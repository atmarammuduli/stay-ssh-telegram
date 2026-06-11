import pytest
from unittest.mock import AsyncMock, MagicMock
from stayssh.ssh.tmux import TmuxManager
from stayssh.core.models import CommandResultDTO

@pytest.fixture
def mock_ssh():
    return AsyncMock()

@pytest.fixture
def tmux_manager(mock_ssh):
    return TmuxManager(mock_ssh)

@pytest.mark.asyncio
async def test_check_and_provision_already_exists(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="/usr/bin/tmux", stderr="", duration=0.1)
    success = await tmux_manager.check_and_provision()
    assert success is True
    mock_ssh.run_command.assert_called_with("which tmux")

@pytest.mark.asyncio
async def test_check_and_provision_install_success(tmux_manager, mock_ssh):
    # First call: which tmux fails
    # Second call: sudo apt-get succeeds
    mock_ssh.run_command.side_effect = [
        CommandResultDTO(exit_code=1, stdout="", stderr="", duration=0.1),
        CommandResultDTO(exit_code=0, stdout="installed", stderr="", duration=0.1)
    ]
    success = await tmux_manager.check_and_provision()
    assert success is True
    assert mock_ssh.run_command.call_count == 2

@pytest.mark.asyncio
async def test_check_and_provision_install_failure(tmux_manager, mock_ssh):
    # All calls fail
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="error", duration=0.1)
    success = await tmux_manager.check_and_provision()
    assert success is False
    # 1 for which + 4 for install commands
    assert mock_ssh.run_command.call_count == 5

@pytest.mark.asyncio
async def test_list_sessions_success(tmux_manager, mock_ssh):
    """Verify parsing of tmux ls output."""
    mock_ssh.run_command.return_value = CommandResultDTO(
        exit_code=0, stdout="session1\nsession2\n", stderr="", duration=0.1
    )
    sessions = await tmux_manager.list_sessions()
    assert sessions == ["session1", "session2"]
    mock_ssh.run_command.assert_called_with('tmux ls -F "#{session_name}"')

@pytest.mark.asyncio
async def test_list_sessions_empty(tmux_manager, mock_ssh):
    """Verify empty list when no sessions exist."""
    mock_ssh.run_command.return_value = CommandResultDTO(
        exit_code=1, stdout="", stderr="no server running", duration=0.1
    )
    sessions = await tmux_manager.list_sessions()
    assert sessions == []

@pytest.mark.asyncio
async def test_list_sessions_no_server(tmux_manager, mock_ssh):
    """Verify empty list when no server is running."""
    mock_ssh.run_command.return_value = CommandResultDTO(
        exit_code=1, stdout="", stderr="error connecting to server", duration=0.1
    )
    sessions = await tmux_manager.list_sessions()
    assert sessions == []

@pytest.mark.asyncio
async def test_create_session(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="", stderr="", duration=0.1)
    success = await tmux_manager.create_session("test")
    assert success is True
    mock_ssh.run_command.assert_called_with("tmux new-session -d -s test")

@pytest.mark.asyncio
async def test_create_session_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="error", duration=0.1)
    success = await tmux_manager.create_session("test")
    assert success is False

@pytest.mark.asyncio
async def test_capture_pane(tmux_manager, mock_ssh):
    """Verify capture pane and line counting."""
    mock_ssh.run_command.return_value = CommandResultDTO(
        exit_code=0, stdout="line1\nline2\nline3", stderr="", duration=0.1
    )
    output = await tmux_manager.capture_pane("test")
    assert output.content == "line1\nline2\nline3"
    assert output.line_count == 3
    assert output.session_name == "test"

@pytest.mark.asyncio
async def test_kill_session(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="", stderr="", duration=0.1)
    success = await tmux_manager.kill_session("test")
    assert success is True
    mock_ssh.run_command.assert_called_with("tmux kill-session -t test")

@pytest.mark.asyncio
async def test_kill_session_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="error", duration=0.1)
    success = await tmux_manager.kill_session("test")
    assert success is False

@pytest.mark.asyncio
async def test_send_keys(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="", stderr="", duration=0.1)
    success = await tmux_manager.send_keys("test", "ls")
    assert success is True
    mock_ssh.run_command.assert_called_with('tmux send-keys -t test "ls" C-m')

@pytest.mark.asyncio
async def test_send_keys_no_enter(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="", stderr="", duration=0.1)
    success = await tmux_manager.send_keys("test", "ls", enter=False)
    assert success is True
    mock_ssh.run_command.assert_called_with('tmux send-keys -t test "ls"')

@pytest.mark.asyncio
async def test_send_keys_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="error", duration=0.1)
    success = await tmux_manager.send_keys("test", "ls")
    assert success is False

@pytest.mark.asyncio
async def test_send_raw_key_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="", stderr="", duration=0.1)
    success = await tmux_manager.send_raw_key("test", "C-c")
    assert success is True
    mock_ssh.run_command.assert_called_with('tmux send-keys -t test C-c')

@pytest.mark.asyncio
async def test_send_raw_key_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="error", duration=0.1)
    success = await tmux_manager.send_raw_key("test", "C-c")
    assert success is False

@pytest.mark.asyncio
async def test_capture_pane_failure(tmux_manager, mock_ssh):

    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="error", duration=0.1)
    success = await tmux_manager.send_keys("test", "ls")
    assert success is False

@pytest.mark.asyncio
async def test_capture_pane_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="error", duration=0.1)
    output = await tmux_manager.capture_pane("test")
    assert output is None

@pytest.mark.asyncio
async def test_get_history_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="history", stderr="", duration=0.1)
    history = await tmux_manager.get_history("test")
    assert history == "history"

@pytest.mark.asyncio
async def test_get_history_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="error", duration=0.1)
    history = await tmux_manager.get_history("test")
    assert history is None

@pytest.mark.asyncio
async def test_list_sessions_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="other error", duration=0.1)
    sessions = await tmux_manager.list_sessions()
    assert sessions == []
