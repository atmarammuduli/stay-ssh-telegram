import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from stayssh.db.connection import get_db

@pytest.mark.asyncio
async def test_get_db_yields_session():
    """Verify that get_db yields a session and commits on success."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_factory = MagicMock(return_value=mock_session)
    
    with patch("stayssh.db.connection.async_session_factory", mock_factory):
        async for session in get_db():
            assert session == mock_session
        
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

@pytest.mark.asyncio
async def test_get_db_rollbacks_on_error():
    """Verify that get_db rollbacks if an exception occurs."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_factory = MagicMock(return_value=mock_session)
    
    with patch("stayssh.db.connection.async_session_factory", mock_factory):
        gen = get_db()
        await gen.__anext__()
        try:
            await gen.athrow(ValueError("Test error"))
        except ValueError:
            pass
        
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


