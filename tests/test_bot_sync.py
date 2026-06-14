import pytest
from unittest.mock import AsyncMock, patch
from tmux_ssh_telegram.bot.sync import SyncService
from tmux_ssh_telegram.core.models import SessionDTO, SessionStatus
from datetime import datetime

@pytest.fixture
def mock_session_repo():
    return AsyncMock()

@pytest.fixture
def mock_tmux_manager():
    return AsyncMock()

@pytest.fixture
def sync_service(mock_session_repo, mock_tmux_manager):
    return SyncService(mock_session_repo, mock_tmux_manager)

@pytest.mark.asyncio
async def test_sync_on_startup_success(sync_service, mock_session_repo, mock_tmux_manager):
    mock_tmux_manager.list_sessions.return_value = ["s1"]
    
    # Session not in DB
    mock_session_repo.get_all.return_value = []
    
    await sync_service.sync_on_startup(admin_id=1)
    
    mock_session_repo.create.assert_called_once()

@pytest.mark.asyncio
async def test_sync_on_startup_revive_dead(sync_service, mock_session_repo, mock_tmux_manager):
    mock_tmux_manager.list_sessions.return_value = ["s1"]
    
    # Session exists in DB as DEAD
    db_session = SessionDTO(id=1, name="s1", status=SessionStatus.DEAD, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
    mock_session_repo.get_all.return_value = [db_session]
    
    await sync_service.sync_on_startup(admin_id=1)
    
    mock_session_repo.update_status.assert_called_with(1, SessionStatus.ACTIVE)

@pytest.mark.asyncio
async def test_sync_on_startup_mark_dead(sync_service, mock_session_repo, mock_tmux_manager):
    mock_tmux_manager.list_sessions.return_value = []
    
    # Session exists in DB as ACTIVE
    db_session = SessionDTO(id=1, name="s1", status=SessionStatus.ACTIVE, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
    mock_session_repo.get_all.return_value = [db_session]
    
    await sync_service.sync_on_startup(admin_id=1)
    
    mock_session_repo.update_status.assert_called_with(1, SessionStatus.DEAD)

@pytest.mark.asyncio
async def test_sync_aborted_on_connection_error(sync_service, mock_session_repo, mock_tmux_manager):
    mock_tmux_manager.list_sessions.side_effect = ConnectionError("SSH failed")
    
    # Should not raise exception, just log and return
    await sync_service.sync_on_startup(admin_id=1)
    
    mock_session_repo.get_all.assert_not_called()
