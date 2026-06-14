import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from tmux_ssh_telegram.bot.main import setup_logging, output_monitor_task, post_init, main

@pytest.mark.asyncio
async def test_setup_logging():
    with patch("os.makedirs"):
        with patch("logging.getLogger"):
            setup_logging()

@pytest.mark.asyncio
async def test_output_monitor_task():
    from tmux_ssh_telegram.bot.batcher import AdaptiveBatcher
    mock_app = MagicMock()
    mock_batcher = AsyncMock(spec=AdaptiveBatcher)
    mock_app.bot_data = {"batcher": mock_batcher}
    
    with patch("tmux_ssh_telegram.bot.main.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        
        with patch("tmux_ssh_telegram.bot.main.SessionRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_session = MagicMock()
            mock_session.name = "test_session"
            mock_repo.get_active_sessions = AsyncMock(return_value=[mock_session])
            
            with patch("tmux_ssh_telegram.bot.main.tmux_manager") as mock_tmux:
                # 1st call: initial state
                # 2nd call: new content
                # 3rd call: capture pane fails (None) -> hits line 58
                # 4th call: new_count < old_count -> hits line 75 (approx)
                # 5th call: exception to break loop
                mock_output1 = MagicMock()
                mock_output1.content = "line1\nline2"
                mock_output2 = MagicMock()
                mock_output2.content = "line1\nline2\nline3"
                mock_output3 = MagicMock()
                mock_output3.content = "line1" # new_count (1) < old_count (3)
                
                mock_tmux.capture_pane = AsyncMock(side_effect=[mock_output1, mock_output2, None, mock_output3, Exception("stop")])
                
                with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                    mock_sleep.side_effect = [None, None, None, None, Exception("stop loop")]
                    try:
                        await asyncio.wait_for(output_monitor_task(mock_app), timeout=2.0)
                    except (asyncio.TimeoutError, Exception):
                        pass
                
                assert mock_batcher.add_message.called

@pytest.mark.asyncio
async def test_output_monitor_task_exception():
    mock_app = MagicMock()
    mock_batcher = AsyncMock()
    mock_app.bot_data = {"batcher": mock_batcher}
    
    with patch("tmux_ssh_telegram.bot.main.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.main.SessionRepository") as mock_repo_cls:
            # First call raises, second call stops loop
            mock_repo_cls.return_value.get_active_sessions.side_effect = [Exception("loop error"), Exception("stop loop")]
            
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                mock_sleep.side_effect = [None, Exception("stop loop")]
                try:
                    await asyncio.wait_for(output_monitor_task(mock_app), timeout=1.0)
                except (asyncio.TimeoutError, Exception):
                    pass

@pytest.mark.asyncio
async def test_post_init():
    mock_app = MagicMock()
    mock_app.bot_data = {}
    mock_app.bot.send_message = AsyncMock()
    with patch("tmux_ssh_telegram.bot.main.async_session_factory") as mock_factory:
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db
        with patch("tmux_ssh_telegram.bot.main.UserRepository") as mock_user_repo_cls:
            mock_user_repo = mock_user_repo_cls.return_value
            mock_user_repo.get_or_create = AsyncMock()
            with patch("tmux_ssh_telegram.bot.main.SessionRepository"):
                with patch("tmux_ssh_telegram.bot.main.SyncService") as mock_sync_cls:
                    mock_sync = mock_sync_cls.return_value
                    mock_sync.sync_on_startup = AsyncMock()
                    with patch("asyncio.create_task"):
                        with patch("tmux_ssh_telegram.bot.main.AdaptiveBatcher") as mock_batcher_cls:
                            await post_init(mock_app)
                            assert "ssh_manager" in mock_app.bot_data
                            assert "tmux_manager" in mock_app.bot_data
                            assert "batcher" in mock_app.bot_data
                            
                            # Test the telegram_sender passed to AdaptiveBatcher
                            sender = mock_batcher_cls.call_args[0][0]
                            await sender("test message")
                            mock_app.bot.send_message.assert_called_once()

def test_main():
    with patch("tmux_ssh_telegram.bot.main.ApplicationBuilder") as mock_builder:
        mock_app = mock_builder.return_value.token.return_value.post_init.return_value.build.return_value
        with patch("tmux_ssh_telegram.bot.main.setup_logging"):
            main()
            assert mock_app.add_handler.called
            assert mock_app.run_polling.called
