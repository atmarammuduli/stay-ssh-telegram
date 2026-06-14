import pytest
import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from tmux_ssh_telegram.bot.handlers import (
    handle_command, start, unknown_command, send_key, type_text, 
    list_sessions, session_callback, create_session, switch_session, 
    kill_session, confirm_action, show_log, show_status, show_screenshot, 
    manage_config, restart_bot
)
from tmux_ssh_telegram.core.models import SessionDTO, SessionStatus

@pytest.fixture
def mock_update():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 12345
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.from_user.id = 12345
    return update

@pytest.fixture
def mock_context():
    context = MagicMock()
    context.args = []
    context.user_data = {}
    context.bot_data = {}
    return context

@pytest.mark.asyncio
async def test_start_unauthorized(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = 999
    await start(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("🚫 Unauthorized access.")

@pytest.mark.asyncio
async def test_start_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_or_create = AsyncMock()
            await start(mock_update, mock_context)
            mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_unknown_command_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await unknown_command(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_unknown_command_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    await unknown_command(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()

@pytest.mark.asyncio
async def test_send_key_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await send_key(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_send_key_no_args(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = []
    await send_key(mock_update, mock_context)
    assert "Usage: /key" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_send_key_no_active_session(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["Escape"]
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=None))
            await send_key(mock_update, mock_context)
            assert "No active session" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_send_key_session_not_found(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["Escape"]
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)
            await send_key(mock_update, mock_context)
            assert "Selected session not found" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_send_key_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["Escape"]
    mock_tmux = AsyncMock()
    mock_tmux.send_raw_key.return_value = (True, "")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            mock_db.execute = AsyncMock(return_value=mock_result)
            await send_key(mock_update, mock_context)
            mock_tmux.send_raw_key.assert_called_with("s_name", "Escape")

@pytest.mark.asyncio
async def test_send_key_fail(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["Escape"]
    mock_tmux = AsyncMock()
    mock_tmux.send_raw_key.return_value = (False, "error")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            mock_db.execute = AsyncMock(return_value=mock_result)
            await send_key(mock_update, mock_context)
            assert "Key Failed" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_type_text_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await type_text(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_type_text_no_args(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = []
    await type_text(mock_update, mock_context)
    assert "Usage: /type" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_type_text_no_active_session(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["hello"]
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=None))
            await type_text(mock_update, mock_context)
            assert "No active session" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_type_text_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["hello"]
    mock_tmux = AsyncMock()
    mock_tmux.send_keys.return_value = (True, "")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            mock_db.execute = AsyncMock(return_value=mock_result)
            await type_text(mock_update, mock_context)
            mock_tmux.send_keys.assert_called_with("s_name", "hello", enter=False)

@pytest.mark.asyncio
async def test_type_text_fail(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["hello"]
    mock_tmux = AsyncMock()
    mock_tmux.send_keys.return_value = (False, "error")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            mock_db.execute = AsyncMock(return_value=mock_result)
            await type_text(mock_update, mock_context)
            assert "Type Failed" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_list_sessions_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await list_sessions(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_list_sessions_empty(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SessionRepository") as mock_session_repo_cls:
            mock_session_repo = mock_session_repo_cls.return_value
            mock_session_repo.get_active_sessions = AsyncMock(return_value=[])
            with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
                mock_user_repo = mock_user_repo_cls.return_value
                mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock())
                await list_sessions(mock_update, mock_context)
                assert "No active sessions" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_list_sessions_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SessionRepository") as mock_session_repo_cls:
            mock_session_repo = mock_session_repo_cls.return_value
            mock_session = MagicMock(id=1, name="test", status=SessionStatus.ACTIVE)
            mock_session_repo.get_active_sessions = AsyncMock(return_value=[mock_session])
            with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
                mock_user_repo = mock_user_repo_cls.return_value
                mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
                await list_sessions(mock_update, mock_context)
                assert "Available Sessions" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_session_callback_unauthorized(mock_update, mock_context):
    mock_update.callback_query.from_user.id = 999
    await session_callback(mock_update, mock_context)
    mock_update.callback_query.answer.assert_called_with("Unauthorized.", show_alert=True)

@pytest.mark.asyncio
async def test_session_callback_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.callback_query.from_user.id = settings.ADMIN_USER_ID
    mock_update.callback_query.data = "switch_1"
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "s_name"
        mock_db.execute = AsyncMock(return_value=mock_result)
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.set_active_session = AsyncMock()
            await session_callback(mock_update, mock_context)
            assert "Switched to session" in mock_update.callback_query.edit_message_text.call_args[0][0]

@pytest.mark.asyncio
async def test_create_session_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await create_session(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_create_session_no_args(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = []
    await create_session(mock_update, mock_context)
    assert "Usage: /new" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_create_session_exists(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["exists"]
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SessionRepository") as mock_session_repo_cls:
            mock_session_repo = mock_session_repo_cls.return_value
            mock_session_repo.get_by_name = AsyncMock(return_value=MagicMock())
            await create_session(mock_update, mock_context)
            assert "already exists" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_create_session_fail(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["new"]
    mock_tmux = AsyncMock()
    mock_tmux.create_session.return_value = (False, "error")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SessionRepository") as mock_session_repo_cls:
            mock_session_repo = mock_session_repo_cls.return_value
            mock_session_repo.get_by_name = AsyncMock(return_value=None)
            await create_session(mock_update, mock_context)
            assert "Creation Failed" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_create_session_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["new"]
    mock_tmux = AsyncMock()
    mock_tmux.create_session.return_value = (True, "")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SessionRepository") as mock_session_repo_cls:
            mock_session_repo = mock_session_repo_cls.return_value
            mock_session_repo.get_by_name = AsyncMock(return_value=None)
            mock_session_repo.create = AsyncMock(return_value=MagicMock(id=1))
            with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
                mock_user_repo = mock_user_repo_cls.return_value
                mock_user_repo.set_active_session = AsyncMock()
                await create_session(mock_update, mock_context)
                assert "created and selected" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_switch_session_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await switch_session(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_switch_session_no_args(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = []
    await switch_session(mock_update, mock_context)
    assert "Usage: /switch" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_switch_session_not_found(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["test"]
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SessionRepository") as mock_session_repo_cls:
            mock_session_repo = mock_session_repo_cls.return_value
            mock_session_repo.get_by_name = AsyncMock(return_value=None)
            await switch_session(mock_update, mock_context)
            assert "not found" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_switch_session_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["test"]
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SessionRepository") as mock_session_repo_cls:
            mock_session_repo = mock_session_repo_cls.return_value
            mock_session_repo.get_by_name = AsyncMock(return_value=MagicMock(id=1))
            with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
                mock_user_repo = mock_user_repo_cls.return_value
                mock_user_repo.set_active_session = AsyncMock()
                await switch_session(mock_update, mock_context)
                assert "Switched to session" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_kill_session_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await kill_session(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_kill_session_no_args(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = []
    await kill_session(mock_update, mock_context)
    assert "Usage: /kill" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_kill_session_prompt(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["test"]
    await kill_session(mock_update, mock_context)
    assert "Are you sure" in mock_update.message.reply_text.call_args[0][0]
    assert mock_context.user_data["pending_command"]["type"] == "kill"

@pytest.mark.asyncio
async def test_confirm_action_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await confirm_action(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_confirm_action_no_pending(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.user_data = {}
    await confirm_action(mock_update, mock_context)
    assert "No pending action" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_confirm_action_kill_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.user_data = {"pending_command": {"type": "kill", "args": ["test"]}}
    mock_tmux = AsyncMock()
    mock_tmux.kill_session.return_value = (True, "")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SessionRepository") as mock_session_repo_cls:
            mock_session_repo = mock_session_repo_cls.return_value
            mock_session_repo.get_by_name = AsyncMock(return_value=MagicMock(id=1))
            mock_session_repo.update_status = AsyncMock()
            await confirm_action(mock_update, mock_context)
            assert "killed" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_confirm_action_kill_fail(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.user_data = {"pending_command": {"type": "kill", "args": ["test"]}}
    mock_tmux = AsyncMock()
    mock_tmux.kill_session.return_value = (False, "error")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SessionRepository") as mock_session_repo_cls:
            mock_session_repo = mock_session_repo_cls.return_value
            mock_session_repo.get_by_name = AsyncMock(return_value=None)
            await confirm_action(mock_update, mock_context)
            assert "Kill Failed" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_confirm_action_restart(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.user_data = {"pending_command": {"type": "restart", "args": []}}
    with patch("os.execv") as mock_execv:
        with patch("asyncio.sleep", return_value=None):
            await confirm_action(mock_update, mock_context)
            assert "Restarting" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_confirm_action_config(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.user_data = {"pending_command": {"type": "config", "args": ["BATCH_INTERVAL_MS", "3000"]}}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SettingRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.set_value = AsyncMock()
            await confirm_action(mock_update, mock_context)
            assert "updated to" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_show_log_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await show_log(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_show_log_no_active_session(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=None))
            await show_log(mock_update, mock_context)
            assert "No active session" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_show_log_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_tmux = AsyncMock()
    mock_tmux.get_history.return_value = "content"
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            mock_db.execute = AsyncMock(return_value=mock_result)
            await show_log(mock_update, mock_context)
            assert "content" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_show_log_fail(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_tmux = AsyncMock()
    mock_tmux.get_history.return_value = None
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            mock_db.execute = AsyncMock(return_value=mock_result)
            await show_log(mock_update, mock_context)
            assert "Failed to retrieve history" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_show_status_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_ssh = MagicMock()
    mock_ssh.is_connected.return_value = True
    mock_context.bot_data = {"ssh_manager": mock_ssh, "tmux_manager": AsyncMock()}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            mock_db.execute = AsyncMock(return_value=mock_result)
            await show_status(mock_update, mock_context)
            assert "🟢 Connected" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_show_status_no_active(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_ssh = MagicMock()
    mock_ssh.is_connected.return_value = False
    mock_context.bot_data = {"ssh_manager": mock_ssh, "tmux_manager": AsyncMock()}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=None))
            await show_status(mock_update, mock_context)
            assert "🔴 Disconnected" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_show_screenshot_no_session(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = []
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=None))
            await show_screenshot(mock_update, mock_context)
            assert "No session specified" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_show_screenshot_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["arg_name"]
    mock_tmux = AsyncMock()
    mock_tmux.capture_pane.return_value = MagicMock(content="shot")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        await show_screenshot(mock_update, mock_context)
        assert "shot" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_show_screenshot_fail(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["name"]
    mock_tmux = AsyncMock()
    mock_tmux.capture_pane.return_value = None
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        await show_screenshot(mock_update, mock_context)
        assert "Failed to capture screenshot" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_manage_config_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await manage_config(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_manage_config_list(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = []
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SettingRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_value = AsyncMock(return_value="500")
            await manage_config(mock_update, mock_context)
            assert "Current Settings" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_manage_config_invalid_key(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["set", "INVALID", "val"]
    await manage_config(mock_update, mock_context)
    assert "Invalid setting key" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_manage_config_usage(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["set", "BATCH_INTERVAL_MS"]
    await manage_config(mock_update, mock_context)
    assert "Usage: /config" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_manage_config_prompt(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = ["set", "BATCH_INTERVAL_MS", "3000"]
    await manage_config(mock_update, mock_context)
    assert "Are you sure" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_restart_bot_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await restart_bot(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_restart_bot_prompt(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    await restart_bot(mock_update, mock_context)
    assert "Are you sure" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_handle_command_unauthorized(mock_update, mock_context):
    mock_update.effective_user.id = 999
    await handle_command(mock_update, mock_context)
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_handle_command_no_active(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_update.message.text = "ls"
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=None))
            await handle_command(mock_update, mock_context)
            assert "No active session" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_handle_command_session_not_found(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_update.message.text = "ls"
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)
            await handle_command(mock_update, mock_context)
            assert "Selected session not found" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_handle_command_success(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_update.message.text = "ls"
    mock_tmux = AsyncMock()
    mock_tmux.send_keys.return_value = (True, "")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            mock_db.execute = AsyncMock(return_value=mock_result)
            await handle_command(mock_update, mock_context)
            mock_tmux.send_keys.assert_called_with("s_name", "ls")

@pytest.mark.asyncio
async def test_show_screenshot_from_active(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_context.args = []
    mock_tmux = AsyncMock()
    mock_tmux.capture_pane.return_value = MagicMock(content="shot")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "active_s"
            mock_db.execute = AsyncMock(return_value=mock_result)
            await show_screenshot(mock_update, mock_context)
            assert "shot" in mock_update.message.reply_text.call_args[0][0]
            mock_tmux.capture_pane.assert_called_with("active_s")

@pytest.mark.asyncio
async def test_confirm_action_config_reload_fail(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    # Trigger except Exception: pass at line 284
    mock_context.user_data = {"pending_command": {"type": "config", "args": ["ADMIN_USER_ID", "not_an_int"]}}
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.SettingRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.set_value = AsyncMock()
            await confirm_action(mock_update, mock_context)
            assert "updated to" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_handle_command_fail(mock_update, mock_context):
    from tmux_ssh_telegram.bot.handlers import settings
    mock_update.effective_user.id = settings.ADMIN_USER_ID
    mock_update.message.text = "ls"
    mock_tmux = AsyncMock()
    mock_tmux.send_keys.return_value = (False, "error")
    mock_context.bot_data = {"tmux_manager": mock_tmux}
    
    with patch("tmux_ssh_telegram.bot.handlers.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.handlers.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(active_session_id=1))
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "s_name"
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            await handle_command(mock_update, mock_context)
            assert "Command Failed" in mock_update.message.reply_text.call_args[0][0]
