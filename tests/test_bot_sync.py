import pytest
from unittest.mock import AsyncMock, MagicMock
from stayssh.bot.sync import SyncService
from stayssh.core.models import SessionDTO, SessionStatus
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
async def test_sync_on_startup(sync_service, mock_session_repo, mock_tmux_manager):
    # Host has session1, session2
    mock_tmux_manager.list_sessions.return_value = ["session1", "session2"]
    
    # DB has session2, session3
    db_session2 = SessionDTO(id=2, name="session2", status=SessionStatus.ACTIVE, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
    db_session3 = SessionDTO(id=3, name="session3", status=SessionStatus.ACTIVE, creator_id=1, last_activity=datetime.utcnow(), created_at=datetime.utcnow())
    mock_session_repo.get_active_sessions.return_value = [db_session2, db_session3]
    
    await sync_service.sync_on_startup(admin_id=1)
    
    # Verify session1 (new on host) was created in DB
    mock_session_repo.create.assert_called_once_with(
        name="session1", creator_id=1, description="Discovered from host on startup"
    )
    
    # Verify session3 (missing on host) was marked as DEAD
    mock_session_repo.update_status.assert_called_once_with(3, SessionStatus.DEAD)
