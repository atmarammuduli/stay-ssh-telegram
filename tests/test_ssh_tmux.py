import pytest
from unittest.mock import AsyncMock, patch
from tmux_ssh_telegram.ssh.tmux import TmuxManager
from tmux_ssh_telegram.core.models import CommandResultDTO, TmuxOutputDTO

@pytest.fixture
def mock_ssh():
    return AsyncMock()

@pytest.fixture
def tmux_manager(mock_ssh):
    return TmuxManager(mock_ssh)

@pytest.mark.asyncio
async def test_check_and_provision_already_exists(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="/usr/bin/tmux", stderr="", duration=0.1)
    assert await tmux_manager.check_and_provision() is True
    mock_ssh.run_command.assert_called_with("which tmux")

@pytest.mark.asyncio
async def test_check_and_provision_install_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.side_effect = [
        CommandResultDTO(exit_code=1, stdout="", stderr="", duration=0.1),
        CommandResultDTO(exit_code=0, stdout="installed", stderr="", duration=0.1)
    ]
    assert await tmux_manager.check_and_provision() is True
    assert mock_ssh.run_command.call_count == 2

@pytest.mark.asyncio
async def test_check_and_provision_install_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="error", duration=0.1)
    assert await tmux_manager.check_and_provision() is False
    assert mock_ssh.run_command.call_count == 5

@pytest.mark.asyncio
async def test_list_sessions_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="session1\nsession2\n", stderr="", duration=0.1)
    assert await tmux_manager.list_sessions() == ["session1", "session2"]
    mock_ssh.run_command.assert_called_with('tmux ls -F "#{session_name}"')

@pytest.mark.asyncio
async def test_list_sessions_empty(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="no server running", duration=0.1)
    assert await tmux_manager.list_sessions() == []

@pytest.mark.asyncio
async def test_list_sessions_error(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="other error", duration=0.1)
    with pytest.raises(ConnectionError):
        await tmux_manager.list_sessions()

@pytest.mark.asyncio
async def test_create_session_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="", stderr="", duration=0.1)
    success, error = await tmux_manager.create_session("s1")
    assert success is True and error == ""

@pytest.mark.asyncio
async def test_create_session_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="err", duration=0.1)
    success, error = await tmux_manager.create_session("s1")
    assert success is False and "err" in error

@pytest.mark.asyncio
async def test_kill_session_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="", stderr="", duration=0.1)
    success, error = await tmux_manager.kill_session("s1")
    assert success is True and error == ""

@pytest.mark.asyncio
async def test_kill_session_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="err", duration=0.1)
    success, error = await tmux_manager.kill_session("s1")
    assert success is False and "err" in error

@pytest.mark.asyncio
async def test_send_keys_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="", stderr="", duration=0.1)
    success, error = await tmux_manager.send_keys("s1", "cmd")
    assert success is True and error == ""

@pytest.mark.asyncio
async def test_send_keys_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="err", duration=0.1)
    success, error = await tmux_manager.send_keys("s1", "cmd")
    assert success is False and "err" in error

@pytest.mark.asyncio
async def test_send_raw_key_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="", stderr="", duration=0.1)
    success, error = await tmux_manager.send_raw_key("s1", "C-c")
    assert success is True and error == ""

@pytest.mark.asyncio
async def test_send_raw_key_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="err", duration=0.1)
    success, error = await tmux_manager.send_raw_key("s1", "C-c")
    assert success is False and "err" in error

@pytest.mark.asyncio
async def test_capture_pane_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="l1\nl2\n", stderr="", duration=0.1)
    output = await tmux_manager.capture_pane("s1")
    assert output is not None
    assert output.content == "l1\nl2"
    assert output.line_count == 2

@pytest.mark.asyncio
async def test_capture_pane_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="err", duration=0.1)
    assert await tmux_manager.capture_pane("s1") is None

@pytest.mark.asyncio
async def test_get_history_success(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=0, stdout="hist", stderr="", duration=0.1)
    assert await tmux_manager.get_history("s1") == "hist"

@pytest.mark.asyncio
async def test_get_history_failure(tmux_manager, mock_ssh):
    mock_ssh.run_command.return_value = CommandResultDTO(exit_code=1, stdout="", stderr="err", duration=0.1)
    assert await tmux_manager.get_history("s1") is None
