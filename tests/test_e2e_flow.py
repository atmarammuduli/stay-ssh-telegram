import pytest
import pytest_asyncio
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import text
from telegram import Update, Message, User as TGUser, constants
from telegram.ext import ContextTypes

from tmux_ssh_telegram.ssh.manager import SSHManager
from tmux_ssh_telegram.ssh.tmux import TmuxManager
from tmux_ssh_telegram.db.connection import engine, async_session_factory
from tmux_ssh_telegram.db.models import Base
from tmux_ssh_telegram.db.repositories import SessionRepository, UserRepository, SettingRepository
from tmux_ssh_telegram.core.config import settings
from tmux_ssh_telegram.bot.main import (
    start, list_sessions, create_session, switch_session, 
    kill_session, show_log, manage_config, handle_command,
    send_key, type_text
)

RUN_E2E = os.getenv("RUN_E2E", "false").lower() == "true"

@pytest_asyncio.fixture(autouse=True)
async def setup_e2e_db():
    if not RUN_E2E:
        pytest.skip("RUN_E2E=true not set")
        
    # Ensure DB is initialized and clean
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE TABLE users, sessions, settings CASCADE"))
        # Ensure admin user exists
        await conn.execute(
            text("INSERT INTO users (id, is_admin, created_at) VALUES (:id, :is_admin, now())"),
            {"id": settings.ADMIN_USER_ID, "is_admin": True}
        )
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE users, sessions, settings CASCADE"))

@pytest.fixture
def mock_tg():
    mock_update = MagicMock(spec=Update)
    mock_update.effective_user = MagicMock(spec=TGUser)
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_update.message = AsyncMock(spec=Message)
    
    mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    mock_context.args = []
    return mock_update, mock_context

@pytest.mark.asyncio
async def test_complete_bot_flow_e2e(mock_tg):
    """E2E: Tests the entire bot command lifecycle on a real host."""
    mock_update, mock_context = mock_tg
    ssh_manager = SSHManager()
    tmux_manager = TmuxManager(ssh_manager)
    
    try:
        connected = await ssh_manager.connect()
        assert connected, "Failed to connect to host SSH"
        
        # 1. /start
        await start(mock_update, mock_context)
        
        # 2. /new
        session_name = f"e2e_new_{int(asyncio.get_event_loop().time())}"
        mock_context.args = [session_name]
        await create_session(mock_update, mock_context)
        
        sessions = await tmux_manager.list_sessions()
        assert session_name in sessions
        
        # 3. Command
        mock_update.message.text = "echo 'E2E_WORKS'"
        await handle_command(mock_update, mock_context)
        await asyncio.sleep(1)
        
        # 4. /log
        mock_context.args = ["5"]
        await show_log(mock_update, mock_context)
        args, _ = mock_update.message.reply_text.call_args
        assert "E2E_WORKS" in args[0]
        
        # 5. /key
        mock_context.args = ["C-c"]
        await send_key(mock_update, mock_context)
        
        # 6. /kill
        mock_context.args = [session_name]
        await kill_session(mock_update, mock_context)
        
        sessions = await tmux_manager.list_sessions()
        assert session_name not in sessions
        
    finally:
        await ssh_manager.close()
