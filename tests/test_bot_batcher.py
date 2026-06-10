import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from stayssh.bot.batcher import AdaptiveBatcher
from stayssh.core.config import settings

@pytest.fixture
def mock_send():
    return AsyncMock()

@pytest.fixture
def batcher(mock_send):
    return AdaptiveBatcher(mock_send)

@pytest.mark.asyncio
async def test_batcher_immediate_delivery(batcher, mock_send):
    """Verify immediate delivery when idle."""
    await batcher.add_message("session1", "hello")
    mock_send.assert_called_once_with("<code>hello</code>")
    assert batcher.buffer == {}

@pytest.mark.asyncio
async def test_batcher_burst_delivery(batcher, mock_send):
    """Verify batching when multiple messages arrive quickly."""
    # Force last_sent_at to now to simulate non-idle state
    batcher.last_sent_at = datetime.utcnow()
    
    await batcher.add_message("session1", "line1")
    await batcher.add_message("session1", "line2")
    
    # Send should not be called immediately
    mock_send.assert_not_called()
    assert "session1" in batcher.buffer
    
    # Wait for flush (settings.BATCH_INTERVAL_MS is 2000ms by default)
    # We can speed this up for testing by mocking settings or the sleep
    with patch("asyncio.sleep", return_value=None):
        await batcher._delayed_flush()
        
    mock_send.assert_called_once_with("<code>line1\nline2</code>")

@pytest.mark.asyncio
async def test_batcher_multi_session_headers(batcher, mock_send):
    """Verify session headers when multiple sessions are batched."""
    batcher.last_sent_at = datetime.utcnow()
    
    await batcher.add_message("session1", "msg1")
    await batcher.add_message("session2", "msg2")
    
    with patch("asyncio.sleep", return_value=None):
        await batcher._delayed_flush()
        
    sent_text = mock_send.call_args[0][0]
    assert "<b>[Session: session1]</b>" in sent_text
    assert "<b>[Session: session2]</b>" in sent_text

@pytest.mark.asyncio
async def test_batcher_empty_message(batcher, mock_send):
    await batcher.add_message("session1", " ")
    mock_send.assert_not_called()

@pytest.mark.asyncio
async def test_batcher_send_failure(batcher, mock_send):
    mock_send.side_effect = Exception("Send failed")
    await batcher.add_message("session1", "hello")
    # Should not crash
    mock_send.assert_called_once()
