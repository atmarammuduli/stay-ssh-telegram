import pytest
import os
import asyncio
from sqlalchemy import text
from stayssh.ssh.manager import SSHManager
from stayssh.ssh.tmux import TmuxManager
from stayssh.db.connection import engine
from stayssh.db.models import Base
from stayssh.core.config import settings

RUN_E2E = os.getenv("RUN_E2E", "false").lower() == "true"

@pytest.mark.skipif(not RUN_E2E, reason="RUN_E2E=true not set")
class TestE2EFlow:
    @pytest.fixture(autouse=True)
    async def setup_e2e(self):
        # Ensure DB is ready
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Clean data
            await conn.execute(text("TRUNCATE TABLE users, sessions, settings CASCADE"))
        
        self.ssh_manager = SSHManager()
        self.tmux_manager = TmuxManager(self.ssh_manager)
        
        yield
        
        await self.ssh_manager.close()
        async with engine.begin() as conn:
            # Clean data
            await conn.execute(text("TRUNCATE TABLE users, sessions, settings CASCADE"))


    @pytest.mark.asyncio
    async def test_ssh_tmux_persistence(self):
        """E2E: Create a tmux session, send command, and verify output via real SSH."""
        session_name = f"e2e_test_{int(asyncio.get_event_loop().time())}"
        
        # 1. Connect and Create Session
        connected = await self.ssh_manager.connect()
        assert connected, "Failed to connect to host SSH"
        
        success = await self.tmux_manager.create_session(session_name)
        assert success, f"Failed to create tmux session {session_name}"
        
        try:
            # 2. Send Command
            await self.tmux_manager.send_keys(session_name, "echo 'E2E_VERIFY_SUCCESS'")
            await asyncio.sleep(1) # Wait for execution
            
            # 3. Capture Output
            output = await self.tmux_manager.capture_pane(session_name)
            assert "E2E_VERIFY_SUCCESS" in output.content
            
            # 4. List Sessions
            sessions = await self.tmux_manager.list_sessions()
            assert session_name in sessions
            
        finally:
            # 5. Cleanup
            await self.tmux_manager.kill_session(session_name)
