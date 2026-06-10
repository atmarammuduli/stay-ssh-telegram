import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User as TGUser, Message, constants
from telegram.ext import ContextTypes
from stayssh.bot.main import start, list_sessions, create_session, switch_session, kill_session, show_log, handle_command, manage_config, restart_bot, output_monitor_task, post_init
from stayssh.core.models import SessionDTO, SessionStatus, TmuxOutputDTO
from datetime import datetime

@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TGUser)
    update.effective_user.id = 1 # Match settings.ADMIN_USER_ID
    update.message = AsyncMock(spec=Message)
    return update

@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context

@pytest.fixture(autouse=True)
def patch_settings():
    with patch("stayssh.bot.main.settings") as mock_settings:
        mock_settings.ADMIN_USER_ID = 1
        mock_settings.LOG_DIR = "./logs"
        mock_settings.LOG_LEVEL = "INFO"
        mock_settings.POLL_INTERVAL_MS = 100
        # Make it behave like a real object for hasattr
        mock_settings.BATCH_INTERVAL_MS = 2000
        mock_settings.IDLE_THRESHOLD_MS = 5000
        yield mock_settings

@pytest.fixture
def mock_db_session():
    session = MagicMock()
    # execute returns a result that is sync
    mock_result = MagicMock()
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    # Mocking the context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session

@pytest.fixture
def patch_db(mock_db_session):
    with patch("stayssh.bot.main.async_session_factory", return_value=mock_db_session):
        yield mock_db_session

@pytest.mark.asyncio
async def test_start_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await start(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("🚫 Unauthorized access.")

@pytest.mark.asyncio
async def test_start_authorized(mock_update, mock_context, patch_db):
    await start(mock_update, mock_context)
    assert mock_update.message.reply_text.called

@pytest.mark.asyncio
async def test_list_sessions(mock_update, mock_context):
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.list_sessions = AsyncMock(return_value=["s1"])
        await list_sessions(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "s1" in args[0]

@pytest.mark.asyncio
async def test_create_session_success(mock_update, mock_context, patch_db):
    mock_context.args = ["new_s"]
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.create_session = AsyncMock(return_value=True)
        # Mock SessionRepository.create and UserRepository.set_active_session
        mock_session = SessionDTO(id=1, name="new_s", status=SessionStatus.ACTIVE, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
        with patch("stayssh.db.repositories.SessionRepository.create", return_value=mock_session):
            with patch("stayssh.db.repositories.UserRepository.set_active_session", return_value=None):
                await create_session(mock_update, mock_context)
                args, kwargs = mock_update.message.reply_text.call_args
                assert "created" in args[0]

@pytest.mark.asyncio
async def test_switch_session_success(mock_update, mock_context, patch_db):
    mock_context.args = ["existing_s"]
    mock_session = SessionDTO(id=1, name="existing_s", status=SessionStatus.ACTIVE, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
    with patch("stayssh.db.repositories.SessionRepository.get_by_name", return_value=mock_session):
        with patch("stayssh.db.repositories.UserRepository.set_active_session", return_value=None):
            await switch_session(mock_update, mock_context)
            args, kwargs = mock_update.message.reply_text.call_args
            assert "Switched" in args[0]

@pytest.mark.asyncio
async def test_kill_session_success(mock_update, mock_context, patch_db):
    mock_context.args = ["to_kill"]
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.kill_session = AsyncMock(return_value=True)
        mock_session = SessionDTO(id=1, name="to_kill", status=SessionStatus.ACTIVE, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
        with patch("stayssh.db.repositories.SessionRepository.get_by_name", return_value=mock_session):
            with patch("stayssh.db.repositories.SessionRepository.update_status", return_value=None):
                await kill_session(mock_update, mock_context)
                args, kwargs = mock_update.message.reply_text.call_args
                assert "killed" in args[0]

@pytest.mark.asyncio
async def test_show_log_success(mock_update, mock_context, patch_db):
    mock_context.args = ["10"]
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.get_history = AsyncMock(return_value="some log")
        
        # Mock User model
        mock_user = MagicMock()
        mock_user.active_session_id = 1
        
        with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
            # Mock the DB fetch for session_name
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            patch_db.execute = AsyncMock(return_value=mock_result)
            
            await show_log(mock_update, mock_context)
            args, kwargs = mock_update.message.reply_text.call_args
            assert "some log" in args[0]

@pytest.mark.asyncio
async def test_manage_config_show(mock_update, mock_context, patch_db):
    with patch("stayssh.db.repositories.SettingRepository.get_value", return_value=None):
        await manage_config(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "Current Settings" in args[0]

@pytest.mark.asyncio
async def test_manage_config_set_success(mock_update, mock_context, patch_db):
    mock_context.args = ["set", "BATCH_INTERVAL_MS", "3000"]
    with patch("stayssh.db.repositories.SettingRepository.set_value", return_value=None):
        await manage_config(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "updated" in args[0]

@pytest.mark.asyncio
async def test_manage_config_invalid_key(mock_update, mock_context, patch_db):
    mock_context.args = ["set", "INVALID_KEY", "123"]
    # Ensure hasattr returns False for INVALID_KEY
    with patch("stayssh.bot.main.settings", spec=True) as mock_settings:
        mock_settings.ADMIN_USER_ID = 1
        del mock_settings.INVALID_KEY
        await manage_config(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "Invalid" in args[0]

@pytest.mark.asyncio
async def test_manage_config_invalid_usage(mock_update, mock_context):
    mock_context.args = ["invalid"]
    await manage_config(mock_update, mock_context)
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Usage" in args[0]

@pytest.mark.asyncio
async def test_kill_session_failure(mock_update, mock_context):
    mock_context.args = ["fail_s"]
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.kill_session = AsyncMock(return_value=False)
        await kill_session(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "Failed" in args[0]

@pytest.mark.asyncio
async def test_restart_bot(mock_update, mock_context):
    with patch("os._exit") as mock_exit:
        await restart_bot(mock_update, mock_context)
        assert mock_update.message.reply_text.called
        mock_exit.assert_called_once_with(0)

@pytest.mark.asyncio
async def test_handle_command_success(mock_update, mock_context, patch_db):
    mock_update.message.text = "ls"
    # Mock user fetch
    mock_user = MagicMock()
    mock_user.active_session_id = 1
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        # Mock session name fetch
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "s_name"
        patch_db.execute = AsyncMock(return_value=mock_result)
        
        with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
            mock_tmux.send_keys = AsyncMock(return_value=True)
            await handle_command(mock_update, mock_context)
            mock_tmux.send_keys.assert_called_once_with("s_name", "ls")

@pytest.mark.asyncio
async def test_output_monitor_task(mock_update):
    # Mock application
    mock_app = MagicMock()
    
    # Mock session data
    mock_session = SessionDTO(id=1, name="s1", status=SessionStatus.ACTIVE, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
    
    with patch("stayssh.bot.main.async_session_factory") as mock_db:
        mock_session_obj = AsyncMock()
        mock_session_obj.__aenter__.return_value = mock_session_obj
        mock_db.return_value = mock_session_obj
        
        with patch("stayssh.db.repositories.SessionRepository.get_active_sessions", return_value=[mock_session]):
            with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
                mock_tmux.capture_pane = AsyncMock(return_value=TmuxOutputDTO(session_name="s1", content="line1\nline2", line_count=2))
                
                with patch("stayssh.bot.main.batcher", spec=True) as mock_batcher:
                    mock_batcher.add_message = AsyncMock()
                    
                    # We only want one loop iteration for testing
                    with patch("asyncio.sleep", side_effect=[None, Exception("Stop loop")]):
                        try:
                            await output_monitor_task(mock_app)
                        except Exception as e:
                            if str(e) != "Stop loop": raise
                    
                    mock_batcher.add_message.assert_called()

@pytest.mark.asyncio
async def test_post_init(patch_db):
    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()
    
    # Mock repositories and sync service
    with patch("stayssh.bot.main.SyncService") as mock_sync_cls:
        mock_sync_inst = mock_sync_cls.return_value
        mock_sync_inst.sync_on_startup = AsyncMock()
        
        with patch("asyncio.create_task") as mock_create_task:
            await post_init(mock_app)
            
            mock_sync_inst.sync_on_startup.assert_called_once()
            mock_create_task.assert_called_once()
            assert mock_app.bot.send_message is not None # Batcher initialization
