import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from tmux_ssh_telegram.core.config import settings

logger = logging.getLogger(__name__)

class AdaptiveBatcher:
    """
    Handles message delivery with adaptive batching.
    - Delivers single messages immediately.
    - Batches concurrent or high-frequency messages to prevent spam.
    """

    def __init__(self, telegram_send_func):
        self.send_func = telegram_send_func
        self.buffer: Dict[str, List[str]] = defaultdict(list)
        self.last_sent_at: Optional[datetime] = None
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        
        # Settings from config
        self.batch_interval = settings.BATCH_INTERVAL_MS / 1000.0
        self.idle_threshold = settings.IDLE_THRESHOLD_MS / 1000.0

    async def add_message(self, session_name: str, text: str) -> None:
        """Adds a message to the batcher."""
        if not text.strip():
            return

        async with self._lock:
            self.buffer[session_name].append(text)
            
            now = datetime.utcnow()
            
            # 1. Decide if we can send immediately (Idle State)
            if self.last_sent_at is None or (now - self.last_sent_at).total_seconds() > self.idle_threshold:
                if len(self.buffer) == 1 and len(self.buffer[session_name]) == 1:
                    logger.debug(f"Idle state detected. Sending message from {session_name} immediately.")
                    await self._flush_now()
                    return

            # 2. Otherwise, ensure a flush task is running (Burst State)
            if not self._flush_task or self._flush_task.done():
                logger.debug(f"Burst state detected. Starting batch timer for {self.batch_interval}s.")
                self._flush_task = asyncio.create_task(self._delayed_flush())

    async def _delayed_flush(self) -> None:
        """Wait for the batch interval and then flush the buffer."""
        await asyncio.sleep(self.batch_interval)
        async with self._lock:
            await self._flush_now()

    async def _flush_now(self) -> None:
        """Sends all buffered messages to Telegram."""
        if not self.buffer:
            return

        # Bundle messages by session
        bundled_messages = []
        for session_name, lines in self.buffer.items():
            content = "\n".join(lines)
            # If batching multiple sessions, add a header
            if len(self.buffer) > 1:
                bundled_messages.append(f"<b>[Session: {session_name}]</b>\n<code>{content}</code>")
            else:
                bundled_messages.append(f"<code>{content}</code>")

        # Join all bundles and send
        final_text = "\n\n".join(bundled_messages)
        
        # Respect Telegram limit (approximate, simpler for now)
        if len(final_text) > 4000:
            final_text = final_text[:3997] + "..."

        try:
            await self.send_func(final_text)
            self.last_sent_at = datetime.utcnow()
        except Exception as e:
            logger.error(f"Failed to send batched message: {e}")
        finally:
            self.buffer.clear()
