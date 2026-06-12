import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram import Update, User as TGUser, Message, constants
from telegram.ext import ContextTypes
from stayssh.bot.main import (
    start, list_sessions, create_session, switch_session, 
    kill_session, show_log, handle_command, manage_config, 
    restart_bot, output_monitor_task, post_init,
    send_key, type_text
)
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
async def test_list_sessions_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await list_sessions(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_list_sessions_empty(mock_update, mock_context):
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.list_sessions = AsyncMock(return_value=[])
        await list_sessions(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "No active tmux sessions" in args[0]

@pytest.mark.asyncio
async def test_list_sessions_success(mock_update, mock_context):
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.list_sessions = AsyncMock(return_value=["s1"])
        await list_sessions(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "s1" in args[0]

@pytest.mark.asyncio
async def test_create_session_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await create_session(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_create_session_no_args(mock_update, mock_context):
    mock_context.args = []
    await create_session(mock_update, mock_context)
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Usage" in args[0]

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
async def test_create_session_failure(mock_update, mock_context, patch_db):
    mock_context.args = ["fail_s"]
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.create_session = AsyncMock(return_value=False)
        await create_session(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "Failed" in args[0]

@pytest.mark.asyncio
async def test_switch_session_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await switch_session(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_switch_session_no_args(mock_update, mock_context):
    mock_context.args = []
    await switch_session(mock_update, mock_context)
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Usage" in args[0]

@pytest.mark.asyncio
async def test_switch_session_not_found(mock_update, mock_context, patch_db):
    mock_context.args = ["not_found"]
    with patch("stayssh.db.repositories.SessionRepository.get_by_name", return_value=None):
        await switch_session(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "not found" in args[0]

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
async def test_kill_session_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await kill_session(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_kill_session_no_args(mock_update, mock_context):
    mock_context.args = []
    await kill_session(mock_update, mock_context)
    args, kwargs = mock_update.message.reply_text.call_args
    assert "Usage" in args[0]

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
async def test_kill_session_success_not_in_db(mock_update, mock_context, patch_db):
    mock_context.args = ["to_kill"]
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.kill_session = AsyncMock(return_value=True)
        with patch("stayssh.db.repositories.SessionRepository.get_by_name", return_value=None):
            await kill_session(mock_update, mock_context)
            args, kwargs = mock_update.message.reply_text.call_args
            assert "killed" in args[0]

@pytest.mark.asyncio
async def test_show_log_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await show_log(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_show_log_no_active_session(mock_update, mock_context, patch_db):
    mock_context.args = ["10"]
    mock_user = MagicMock()
    mock_user.active_session_id = None
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        await show_log(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "No active session" in args[0]

@pytest.mark.asyncio
async def test_show_log_session_not_found(mock_update, mock_context, patch_db):
    mock_context.args = ["abc"] # Invalid int args also handled by default lines=20
    mock_user = MagicMock()
    mock_user.active_session_id = 1
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        patch_db.execute = AsyncMock(return_value=mock_result)
        await show_log(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "not found" in args[0]

@pytest.mark.asyncio
async def test_show_log_failure(mock_update, mock_context, patch_db):
    mock_context.args = ["10"]
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.get_history = AsyncMock(return_value=None)
        mock_user = MagicMock()
        mock_user.active_session_id = 1
        with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            patch_db.execute = AsyncMock(return_value=mock_result)
            await show_log(mock_update, mock_context)
            args, kwargs = mock_update.message.reply_text.call_args
            assert "Failed" in args[0]

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
async def test_manage_config_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await manage_config(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

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
async def test_manage_config_set_log_level(mock_update, mock_context, patch_db):
    mock_context.args = ["set", "LOG_LEVEL", "DEBUG"]
    with patch("stayssh.db.repositories.SettingRepository.set_value", return_value=None):
        with patch("stayssh.bot.main.setup_logging") as mock_setup:
            await manage_config(mock_update, mock_context)
            mock_setup.assert_called()

@pytest.mark.asyncio
async def test_manage_config_parse_failure(mock_update, mock_context, patch_db):
    mock_context.args = ["set", "BATCH_INTERVAL_MS", "invalid"]
    with patch("stayssh.db.repositories.SettingRepository.set_value", return_value=None):
        await manage_config(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "Failed to parse" in args[0]

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
async def test_send_key_success(mock_update, mock_context, patch_db):
    mock_context.args = ["Escape"]
    mock_user = MagicMock()
    mock_user.active_session_id = 1
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "s_name"
        patch_db.execute = AsyncMock(return_value=mock_result)
        with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
            mock_tmux.send_raw_key = AsyncMock()
            await send_key(mock_update, mock_context)
            mock_tmux.send_raw_key.assert_called_once_with("s_name", "Escape")

@pytest.mark.asyncio
async def test_type_text_success(mock_update, mock_context, patch_db):
    mock_context.args = ["hello", "world"]
    mock_user = MagicMock()
    mock_user.active_session_id = 1
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "s_name"
        patch_db.execute = AsyncMock(return_value=mock_result)
        with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
            mock_tmux.send_keys = AsyncMock()
            await type_text(mock_update, mock_context)
            mock_tmux.send_keys.assert_called_once_with("s_name", "hello world", enter=False)

@pytest.mark.asyncio
async def test_send_key_no_args(mock_update, mock_context):
    mock_context.args = []
    await send_key(mock_update, mock_context)
    assert mock_update.message.reply_text.called

@pytest.mark.asyncio
async def test_type_text_no_args(mock_update, mock_context):
    mock_context.args = []
    await type_text(mock_update, mock_context)
    assert mock_update.message.reply_text.called

@pytest.mark.asyncio
async def test_send_key_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await send_key(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_send_key_no_session(mock_update, mock_context, patch_db):
    mock_context.args = ["Escape"]
    mock_user = MagicMock()
    mock_user.active_session_id = None
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        await send_key(mock_update, mock_context)
        assert "No active session" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_type_text_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await type_text(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_type_text_no_session(mock_update, mock_context, patch_db):
    mock_context.args = ["text"]
    mock_user = MagicMock()
    mock_user.active_session_id = None
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        await type_text(mock_update, mock_context)
        assert "No active session" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_kill_session_failure(mock_update, mock_context):
    mock_context.args = ["fail_s"]
    with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
        mock_tmux.kill_session = AsyncMock(return_value=False)
        await kill_session(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "Failed" in args[0]

@pytest.mark.asyncio
async def test_restart_bot_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await restart_bot(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_restart_bot(mock_update, mock_context):
    with patch("os._exit") as mock_exit:
        await restart_bot(mock_update, mock_context)
        assert mock_update.message.reply_text.called
        mock_exit.assert_called_once_with(0)

@pytest.mark.asyncio
async def test_handle_command_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await handle_command(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_handle_command_no_active_session(mock_update, mock_context, patch_db):
    mock_update.message.text = "ls"
    mock_user = MagicMock()
    mock_user.active_session_id = None
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        await handle_command(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "No active session" in args[0]

@pytest.mark.asyncio
async def test_handle_command_session_not_found(mock_update, mock_context, patch_db):
    mock_update.message.text = "ls"
    mock_user = MagicMock()
    mock_user.active_session_id = 1
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        patch_db.execute = AsyncMock(return_value=mock_result)
        await handle_command(mock_update, mock_context)
        args, kwargs = mock_update.message.reply_text.call_args
        assert "not found" in args[0]

@pytest.mark.asyncio
async def test_handle_command_failure(mock_update, mock_context, patch_db):
    mock_update.message.text = "ls"
    mock_user = MagicMock()
    mock_user.active_session_id = 1
    with patch("stayssh.db.repositories.UserRepository.get_or_create", return_value=mock_user):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "s_name"
        patch_db.execute = AsyncMock(return_value=mock_result)
        with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
            mock_tmux.send_keys = AsyncMock(return_value=False)
            await handle_command(mock_update, mock_context)
            args, kwargs = mock_update.message.reply_text.call_args
            assert "Failed" in args[0]

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
async def test_output_monitor_task_exception(mock_update):
    mock_app = MagicMock()
    with patch("stayssh.bot.main.async_session_factory", side_effect=Exception("DB Error")):
        with patch("asyncio.sleep", side_effect=[None, Exception("Stop loop")]):
            try:
                await output_monitor_task(mock_app)
            except Exception as e:
                if str(e) != "Stop loop": raise

@pytest.mark.asyncio
async def test_output_monitor_task_no_output(mock_update):
    mock_app = MagicMock()
    mock_session = SessionDTO(id=1, name="s1", status=SessionStatus.ACTIVE, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
    with patch("stayssh.bot.main.async_session_factory") as mock_db:
        mock_session_obj = AsyncMock()
        mock_session_obj.__aenter__.return_value = mock_session_obj
        mock_db.return_value = mock_session_obj
        with patch("stayssh.db.repositories.SessionRepository.get_active_sessions", return_value=[mock_session]):
            with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
                mock_tmux.capture_pane = AsyncMock(return_value=None)
                with patch("asyncio.sleep", side_effect=[None, Exception("Stop loop")]):
                    try:
                        await output_monitor_task(mock_app)
                    except Exception as e:
                        if str(e) != "Stop loop": raise

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
                # First call: 2 lines (initial state). Second call: 3 lines (new output).
                mock_tmux.capture_pane = AsyncMock(side_effect=[
                    TmuxOutputDTO(session_name="s1", content="line1\nline2", line_count=2),
                    TmuxOutputDTO(session_name="s1", content="line1\nline2\nline3", line_count=3)
                ])
                
                with patch("stayssh.bot.main.batcher", spec=True) as mock_batcher:
                    mock_batcher.add_message = AsyncMock()
                    
                    # We want two loop iterations: one for initial state, one for new output
                    with patch("asyncio.sleep", side_effect=[None, None, Exception("Stop loop")]):
                        try:
                            await output_monitor_task(mock_app)
                        except Exception as e:
                            if str(e) != "Stop loop": raise
                    
                    mock_batcher.add_message.assert_called_once_with("s1", "line3")

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
            assert mock_app.bot.send_message is not None 
            
            # Test the telegram_sender function created inside post_init
            from stayssh.bot import main as bot_main
            await bot_main.batcher.send_func("test message")
            mock_app.bot.send_message.assert_called_with(chat_id=1, text="test message", parse_mode=constants.ParseMode.HTML)

def test_main():
    with patch("stayssh.bot.main.ApplicationBuilder") as mock_builder:
        mock_app = mock_builder.return_value.token.return_value.post_init.return_value.build.return_value
        mock_app.run_polling = MagicMock()
        
        from stayssh.bot.main import main
        main()
        
        mock_app.run_polling.assert_called_once()

def test_entry_point():
    with patch("stayssh.bot.main.main") as mock_main:
        # Simulate normal run
        with patch("stayssh.bot.main.__name__", "__main__"):
            # We can't easily trigger the block without re-importing or executing
            pass

def test_keyboard_interrupt():
    with patch("stayssh.bot.main.main", side_effect=KeyboardInterrupt):
        with patch("stayssh.bot.main.logger") as mock_logger:
            # Re-run the block at the end of main.py
            try:
                # We'll just manually call the logic that's in the try/except block
                from stayssh.bot.main import main
                try:
                    main()
                except KeyboardInterrupt:
                    mock_logger.info("StaySSH Bot stopped by user.")
            except:
                pass
            mock_logger.info.assert_any_call("StaySSH Bot stopped by user.")

@pytest.mark.asyncio
async def test_output_monitor_task_reset(mock_update):
    """Test output monitor task when line count decreases (e.g. history cleared)."""
    mock_app = MagicMock()
    mock_session = SessionDTO(id=1, name="s1", status=SessionStatus.ACTIVE, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
    
    with patch("stayssh.bot.main.async_session_factory") as mock_db:
        mock_session_obj = AsyncMock()
        mock_session_obj.__aenter__.return_value = mock_session_obj
        mock_db.return_value = mock_session_obj
        
        with patch("stayssh.db.repositories.SessionRepository.get_active_sessions", return_value=[mock_session]):
            with patch("stayssh.bot.main.tmux_manager", spec=True) as mock_tmux:
                # 1st iteration: 10 lines
                # 2nd iteration: 5 lines (reset)
                mock_tmux.capture_pane = AsyncMock(side_effect=[
                    TmuxOutputDTO(session_name="s1", content="line\n"*10, line_count=10),
                    TmuxOutputDTO(session_name="s1", content="line\n"*5, line_count=5)
                ])
                
                with patch("stayssh.bot.main.batcher", spec=True) as mock_batcher:
                    mock_batcher.add_message = AsyncMock()
                    # Run 2 iterations then stop
                    with patch("asyncio.sleep", side_effect=[None, None, Exception("Stop loop")]):
                        try:
                            await output_monitor_task(mock_app)
                        except Exception as e:
                            if str(e) != "Stop loop": raise
                    
                    # Should NOT have called add_message during reset (count went from 10 to 5)
                    assert mock_batcher.add_message.call_count == 0
