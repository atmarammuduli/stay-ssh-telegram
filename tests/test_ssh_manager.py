import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncssh
from stayssh.ssh.manager import SSHManager
from stayssh.core.config import settings

@pytest.fixture
def ssh_manager():
    with patch("stayssh.ssh.manager.settings") as mock_settings:
        mock_settings.HOST_SSH_URL = "ssh://testuser@testhost:2222"
        mock_settings.SSH_KEY_PATH = "test_key"
        return SSHManager()

def test_parse_url_no_ssh_prefix(ssh_manager):
    with patch("stayssh.ssh.manager.settings") as mock_settings:
        mock_settings.HOST_SSH_URL = "testuser@testhost"
        mgr = SSHManager()
        assert mgr.username == "testuser"
        assert mgr.host == "testhost"
        assert mgr.port == 22

def test_parse_url_no_user(ssh_manager):
    with patch("stayssh.ssh.manager.settings") as mock_settings:
        mock_settings.HOST_SSH_URL = "testhost"
        mgr = SSHManager()
        assert mgr.username == ""
        assert mgr.host == "testhost"

@pytest.mark.asyncio
async def test_connect_success(ssh_manager):
    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        success = await ssh_manager.connect()
        assert success is True
        assert ssh_manager.connection is not None
        mock_connect.assert_called_once()

@pytest.mark.asyncio
async def test_connect_failure(ssh_manager):
    with patch("asyncssh.connect", side_effect=Exception("Conn failed")):
        success = await ssh_manager.connect()
        assert success is False
        assert ssh_manager.connection is None

@pytest.mark.asyncio
async def test_run_command_success(ssh_manager):
    mock_conn = MagicMock()
    mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0, stdout="ok", stderr=""))
    ssh_manager.connection = mock_conn
    
    result = await ssh_manager.run_command("ls")
    assert result.exit_code == 0
    assert result.stdout == "ok"
    assert result.duration > 0

@pytest.mark.asyncio
async def test_run_command_not_connected(ssh_manager):
    with patch.object(ssh_manager, "connect", return_value=False):
        result = await ssh_manager.run_command("ls")
        assert result.exit_code == -1
        assert "failed" in result.stderr

@pytest.mark.asyncio
async def test_run_command_exception(ssh_manager):
    mock_conn = MagicMock()
    mock_conn.run = AsyncMock(side_effect=Exception("Exec error"))
    ssh_manager.connection = mock_conn
    
    result = await ssh_manager.run_command("ls")
    assert result.exit_code == -1
    assert "Exec error" in result.stderr
    assert ssh_manager.connection is None # Connection reset on error

@pytest.mark.asyncio
async def test_close(ssh_manager):
    mock_conn = MagicMock()
    mock_conn.wait_closed = AsyncMock()
    ssh_manager.connection = mock_conn
    await ssh_manager.close()
    mock_conn.close.assert_called_once()
    mock_conn.wait_closed.assert_called_once()
    assert ssh_manager.connection is None


