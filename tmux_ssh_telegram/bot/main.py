import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from tmux_ssh_telegram.core.config import settings
from tmux_ssh_telegram.db.connection import async_session_factory
from tmux_ssh_telegram.db.repositories import SessionRepository, UserRepository
from tmux_ssh_telegram.ssh.manager import SSHManager
from tmux_ssh_telegram.ssh.tmux import TmuxManager
from tmux_ssh_telegram.bot.sync import SyncService
from tmux_ssh_telegram.bot.batcher import AdaptiveBatcher
from tmux_ssh_telegram.bot import handlers

# Logging Setup
def setup_logging() -> None:
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_file = os.path.join(settings.LOG_DIR, "tmux_ssh_telegram.log")
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

setup_logging()
logger = logging.getLogger(__name__)

# Global Managers for the background loop (still needed here or pass to it)
ssh_manager = SSHManager()
tmux_manager = TmuxManager(ssh_manager)

async def output_monitor_task(application) -> None:
    """Background task to poll tmux output and feed the batcher."""
    logger.info("Starting output monitor task...")
    session_line_counts = {}
    batcher = application.bot_data.get("batcher")

    while True:
        try:
            async with async_session_factory() as db:
                session_repo = SessionRepository(db)
                active_sessions = await session_repo.get_active_sessions()

            for session in active_sessions:
                output_dto = await tmux_manager.capture_pane(session.name)
                if not output_dto:
                    continue

                lines = output_dto.content.splitlines()
                new_count = len(lines)

                if session.name not in session_line_counts:
                    session_line_counts[session.name] = new_count
                    continue

                old_count = session_line_counts[session.name]
                if new_count > old_count:
                    new_content = "\n".join(lines[old_count:])
                    if new_content.strip():
                        await batcher.add_message(session.name, new_content)
                    session_line_counts[session.name] = new_count
                elif new_count < old_count:
                    # Session might have been cleared or restarted
                    session_line_counts[session.name] = new_count

        except Exception as e:
            logger.error(f"Error in output monitor: {e}", exc_info=True)
            
        await asyncio.sleep(settings.POLL_INTERVAL_MS / 1000.0)

async def post_init(application) -> None:
    """Async initialization after the application is built."""
    # Inject managers into bot_data for handlers
    application.bot_data["ssh_manager"] = ssh_manager
    application.bot_data["tmux_manager"] = tmux_manager

    # Initialize Batcher
    from telegram import constants
    async def telegram_sender(text: str):
        await application.bot.send_message(chat_id=settings.ADMIN_USER_ID, text=text, parse_mode=constants.ParseMode.HTML)
    
    batcher = AdaptiveBatcher(telegram_sender)
    application.bot_data["batcher"] = batcher

    # Ensure Admin User Exists
    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        await user_repo.get_or_create(settings.ADMIN_USER_ID, is_admin=True)
        
        session_repo = SessionRepository(db)
        sync_service = SyncService(session_repo, tmux_manager)
        await sync_service.sync_on_startup(settings.ADMIN_USER_ID)
        await db.commit()

    # Background Tasks
    asyncio.create_task(output_monitor_task(application))
    logger.info("StaySSH Bot initialized and background tasks started.")

async def debug_logger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # pragma: no cover
    """Logs all incoming updates for debugging."""
    user = update.effective_user
    text = update.message.text if update.message else "No text"
    logger.info(f"DEBUG: Update from {user.id if user else 'Unknown'}: {text}")

def main() -> None:
    # Initialize Bot
    application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).post_init(post_init).build()
    
    # Handlers
    application.add_handler(MessageHandler(filters.ALL, debug_logger), group=-1)
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("st", handlers.start))
    
    application.add_handler(CommandHandler("sessions", handlers.list_sessions))
    application.add_handler(CommandHandler("ls", handlers.list_sessions))
    
    application.add_handler(CommandHandler("new", handlers.create_session))
    application.add_handler(CommandHandler("n", handlers.create_session))
    
    application.add_handler(CommandHandler("switch", handlers.switch_session))
    application.add_handler(CommandHandler("sw", handlers.switch_session))
    
    application.add_handler(CommandHandler("kill", handlers.kill_session))
    application.add_handler(CommandHandler("k", handlers.kill_session))
    
    application.add_handler(CommandHandler("log", handlers.show_log))
    application.add_handler(CommandHandler("l", handlers.show_log))
    
    application.add_handler(CommandHandler("screenshot", handlers.show_screenshot))
    application.add_handler(CommandHandler("ss", handlers.show_screenshot))
    
    application.add_handler(CommandHandler("key", handlers.send_key))
    application.add_handler(CommandHandler("ky", handlers.send_key))
    
    application.add_handler(CommandHandler("type", handlers.type_text))
    application.add_handler(CommandHandler("t", handlers.type_text))
    
    application.add_handler(CommandHandler("config", handlers.manage_config))
    application.add_handler(CommandHandler("c", handlers.manage_config))
    
    application.add_handler(CommandHandler("status", handlers.show_status))
    application.add_handler(CommandHandler("s", handlers.show_status))
    
    application.add_handler(CommandHandler("restart", handlers.restart_bot))
    application.add_handler(CommandHandler("r", handlers.restart_bot))
    
    application.add_handler(CallbackQueryHandler(handlers.session_callback))
    application.add_handler(CommandHandler("y", handlers.confirm_action))
    
    application.add_handler(MessageHandler(filters.COMMAND, handlers.unknown_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handlers.handle_command))

    logger.info("StaySSH Bot is starting...")
    application.run_polling()

if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except KeyboardInterrupt:
        logger.info("StaySSH Bot stopped by user.")
