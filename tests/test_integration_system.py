import pytest
import pytest_asyncio
import os
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from tmux_ssh_telegram.db.models import Base
from tmux_ssh_telegram.db.repositories import UserRepository, SessionRepository, SettingRepository
from tmux_ssh_telegram.ssh.manager import SSHManager
from tmux_ssh_telegram.ssh.tmux import TmuxManager
from tmux_ssh_telegram.bot.sync import SyncService
from tmux_ssh_telegram.core.config import settings

# Integration tests require a running database and SSH host.
DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION", "false").lower() == "true"

@pytest.mark.skipif(not RUN_INTEGRATION, reason="RUN_INTEGRATION=true not set")
class TestSystemIntegration:
    @pytest_asyncio.fixture(autouse=True)
    async def setup_system(self):
        # 1. Setup DB
        self.engine = create_async_engine(DATABASE_URL)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("TRUNCATE TABLE users, sessions, settings CASCADE"))
            # Ensure admin user exists for foreign key constraints
            await conn.execute(
                text("INSERT INTO users (id, is_admin, created_at) VALUES (:id, :is_admin, now())"),
                {"id": settings.ADMIN_USER_ID, "is_admin": True}
            )
        
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        
        # 2. Setup SSH & Tmux
        self.ssh_manager = SSHManager()
        self.tmux_manager = TmuxManager(self.ssh_manager)
        
        # Ensure a clean state on the host for integration tests
        await self.ssh_manager.connect()
        existing_sessions = await self.tmux_manager.list_sessions()
        for session in existing_sessions:
            if session.startswith("integ_"):
                await self.tmux_manager.kill_session(session)
        
        yield
        
        # Cleanup
        async with self.engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE users, sessions, settings CASCADE"))
        await self.engine.dispose()
        await self.ssh_manager.close()

    @pytest.mark.asyncio
    async def test_full_sync_workflow(self):
        """Tests the integration between DB, SSH, and Tmux discovery/sync."""
        async with self.session_factory() as db:
            user_repo = UserRepository(db)
            session_repo = SessionRepository(db)
            sync_service = SyncService(session_repo, self.tmux_manager)
            
            # Ensure SSH is connected
            connected = await self.ssh_manager.connect()
            assert connected, "Failed to connect to host SSH for integration test"
            
            # 1. Provision Tmux (if needed)
            provisioned = await self.tmux_manager.check_and_provision()
            assert provisioned, "Failed to ensure tmux is present"
            
            # 2. Create multiple sessions on host manually via SSH
            session_names = ["integ_1", "integ_2"]
            for name in session_names:
                await self.tmux_manager.create_session(name)
            
            try:
                # 3. Run Startup Sync
                # This should find the 2 sessions and add them to DB as ACTIVE
                admin_id = settings.ADMIN_USER_ID
                await sync_service.sync_on_startup(admin_id)
                await db.commit()
                
                # 4. Verify DB state
                db_sessions = await session_repo.get_active_sessions()
                db_session_names = [s.name for s in db_sessions]
                for name in session_names:
                    assert name in db_session_names
                
                # 5. Test multi-session interaction
                # Send keys to one session and verify it doesn't affect the other
                await self.tmux_manager.send_keys("integ_1", "echo 'HELLO_INTEG_1'")
                await asyncio.sleep(1)
                
                out1 = await self.tmux_manager.capture_pane("integ_1")
                out2 = await self.tmux_manager.capture_pane("integ_2")
                
                assert "HELLO_INTEG_1" in out1.content
                assert "HELLO_INTEG_1" not in out2.content
                
            finally:
                # Cleanup host sessions
                for name in session_names:
                    await self.tmux_manager.kill_session(name)

    @pytest.mark.asyncio
    async def test_telegram_handlers_integration(self):
        """Tests that bot handlers correctly orchestrate DB and SSH layers."""
        from telegram import Update, Message, User as TGUser
        from telegram.ext import ContextTypes
        from unittest.mock import MagicMock, AsyncMock
        from tmux_ssh_telegram.bot.main import create_session, handle_command
        
        # 1. Setup Mock Update & Context
        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = MagicMock(spec=TGUser)
        mock_update.effective_user.id = settings.ADMIN_USER_ID
        mock_update.message = AsyncMock(spec=Message)
        
        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_context.args = ["integ_handler_test"]
        
        # 2. Call handler: create_session
        # This involves TmuxManager.create_session (SSH) and SessionRepo.create (DB)
        await create_session(mock_update, mock_context)
        
        # 3. Verify side effects
        async with self.session_factory() as db:
            session_repo = SessionRepository(db)
            session = await session_repo.get_by_name("integ_handler_test")
            assert session is not None
            assert session.status == "active"
            
            # Verify it exists on host
            sessions = await self.tmux_manager.list_sessions()
            assert "integ_handler_test" in sessions
            
            # 4. Call handler: handle_command
            mock_update.message.text = "echo 'HANDLER_WORKS'"
            await handle_command(mock_update, mock_context)
            await asyncio.sleep(1)
            
            # Verify output on host
            out = await self.tmux_manager.capture_pane("integ_handler_test")
            assert "HANDLER_WORKS" in out.content
            
        # Cleanup
        await self.tmux_manager.kill_session("integ_handler_test")

    @pytest.mark.asyncio
    async def test_settings_persistence_integration(self):
        """Tests that settings updated in DB are correctly retrieved and handled."""
        async with self.session_factory() as db:
            setting_repo = SettingRepository(db)
            
            # 1. Update a setting
            new_interval = "9999"
            await setting_repo.set_value("BATCH_INTERVAL_MS", new_interval)
            await db.commit()
            
            # 2. Verify retrieval
            val = await setting_repo.get_value("BATCH_INTERVAL_MS")
            assert val == new_interval
