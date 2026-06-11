import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from stayssh.db.repositories import SessionRepository, UserRepository, SettingRepository
from stayssh.db.models import User, Session, Setting
from stayssh.core.models import SessionStatus
from datetime import datetime

@pytest.fixture
def mock_db():
    # Use MagicMock for the session to keep sync methods sync
    session = MagicMock(spec=AsyncSession)
    # Explicitly make async methods AsyncMocks
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session

@pytest.mark.asyncio
async def test_session_repo_get_by_name(mock_db):
    repo = SessionRepository(mock_db)
    mock_session = Session(id=1, name="test", status="active", creator_id=123, created_at=datetime.utcnow(), last_activity=datetime.utcnow())
    
    # Mock SQLAlchemy result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_session
    mock_db.execute.return_value = mock_result
    
    dto = await repo.get_by_name("test")
    assert dto.name == "test"
    assert dto.id == 1

@pytest.mark.asyncio
async def test_session_repo_get_active_sessions(mock_db):
    repo = SessionRepository(mock_db)
    mock_session = Session(id=1, name="test", status="active", creator_id=123, created_at=datetime.utcnow(), last_activity=datetime.utcnow())
    
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_session]
    mock_db.execute.return_value = mock_result
    
    sessions = await repo.get_active_sessions()
    assert len(sessions) == 1
    assert sessions[0].name == "test"

@pytest.mark.asyncio
async def test_user_repo_get_or_create(mock_db):
    repo = UserRepository(mock_db)
    
    # Test existing user
    mock_user = User(id=123, is_admin=False)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result
    
    user = await repo.get_or_create(123)
    assert user.id == 123
    mock_db.add.assert_not_called()
    
    # Test new user
    mock_result.scalar_one_or_none.return_value = None
    user = await repo.get_or_create(456, is_admin=True)
    assert user.id == 456
    assert user.is_admin is True
    mock_db.add.assert_called_once()

@pytest.mark.asyncio
async def test_session_repo_create(mock_db):
    repo = SessionRepository(mock_db)
    dto = await repo.create("new_session", 123)
    assert dto.name == "new_session"
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()

@pytest.mark.asyncio
async def test_session_repo_update_status(mock_db):
    repo = SessionRepository(mock_db)
    await repo.update_status(1, SessionStatus.DEAD)
    mock_db.execute.assert_called_once()

@pytest.mark.asyncio
async def test_user_repo_set_active(mock_db):
    repo = UserRepository(mock_db)
    await repo.set_active_session(123, 1)
    mock_db.execute.assert_called_once()

@pytest.mark.asyncio
async def test_setting_repo_get_value(mock_db):
    repo = SettingRepository(mock_db)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "v"
    mock_db.execute.return_value = mock_result
    
    val = await repo.get_value("k")
    assert val == "v"

@pytest.mark.asyncio
async def test_setting_repo_update(mock_db):
    repo = SettingRepository(mock_db)
    mock_setting = Setting(key="k", value="v")
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_setting
    mock_db.execute.return_value = mock_result
    
    await repo.set_value("k", "v2")
    assert mock_setting.value == "v2"

@pytest.mark.asyncio
async def test_setting_repo_create_new(mock_db):
    repo = SettingRepository(mock_db)
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    await repo.set_value("k", "v")
    mock_db.add.assert_called_once()

