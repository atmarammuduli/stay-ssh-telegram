import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from stayssh.core.config import settings
from stayssh.core.models import SessionStatus
from stayssh.db.connection import async_session_factory
from stayssh.db.repositories import SessionRepository, UserRepository, SettingRepository
from stayssh.ssh.manager import SSHManager
from stayssh.ssh.tmux import TmuxManager
from stayssh.bot.sync import SyncService
from stayssh.bot.batcher import AdaptiveBatcher

# Logging Setup
def setup_logging() -> None:
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_file = os.path.join(settings.LOG_DIR, "stayssh.log")
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Rotating File Handler (10MB per file, keep 5 backups)
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

# Global Managers
ssh_manager = SSHManager()
tmux_manager = TmuxManager(ssh_manager)
batcher: AdaptiveBatcher = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    user = update.effective_user
    if user.id != settings.ADMIN_USER_ID:
        await update.message.reply_text("🚫 Unauthorized access.")
        return

    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        await user_repo.get_or_create(user.id, is_admin=True)
        await db.commit()

    await update.message.reply_text(
        "👋 Welcome to <b>StaySSH</b>!\n\n"
        "Available commands:\n"
        "/new <name> - Create a new session\n"
        "/sessions - List host sessions\n"
        "/switch <name> - Switch active session\n"
        "/kill <name> - Kill a session\n"
        "/log <n> - Show last N lines\n"
        "/status - Show current session info\n\n"
        "Send any text to execute it in the active session.",
        parse_mode=constants.ParseMode.HTML
    )

async def list_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /sessions."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    names = await tmux_manager.list_sessions()
    if not names:
        await update.message.reply_text("ℹ️ No active tmux sessions found on host.")
        return
    
    text = "📂 <b>Active Host Sessions:</b>\n"
    for name in names:
        text += f"• <code>{name}</code>\n"
    
    await update.message.reply_text(text, parse_mode=constants.ParseMode.HTML)

async def create_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /new <name>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /new <name>")
        return
    
    name = context.args[0]
    success = await tmux_manager.create_session(name)
    if success:
        async with async_session_factory() as db:
            session_repo = SessionRepository(db)
            user_repo = UserRepository(db)
            session = await session_repo.create(name, update.effective_user.id)
            await user_repo.set_active_session(update.effective_user.id, session.id)
            await db.commit()
        await update.message.reply_text(f"✅ Session '<code>{name}</code>' created and selected.", parse_mode=constants.ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Failed to create session '<code>{name}</code>'.", parse_mode=constants.ParseMode.HTML)

async def switch_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /switch <name>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /switch <name>")
        return
    
    name = context.args[0]
    async with async_session_factory() as db:
        session_repo = SessionRepository(db)
        user_repo = UserRepository(db)
        session = await session_repo.get_by_name(name)
        
        if not session:
            await update.message.reply_text(f"❌ Session '<code>{name}</code>' not found in database.", parse_mode=constants.ParseMode.HTML)
            return
        
        await user_repo.set_active_session(update.effective_user.id, session.id)
        await db.commit()
    
    await update.message.reply_text(f"🎯 Switched to session '<code>{name}</code>'.", parse_mode=constants.ParseMode.HTML)

async def kill_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /kill <name>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /kill <name>")
        return
    
    name = context.args[0]
    success = await tmux_manager.kill_session(name)
    if success:
        async with async_session_factory() as db:
            session_repo = SessionRepository(db)
            session = await session_repo.get_by_name(name)
            if session:
                await session_repo.update_status(session.id, SessionStatus.DEAD)
                await db.commit()
        await update.message.reply_text(f"💀 Session '<code>{name}</code>' killed.", parse_mode=constants.ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Failed to kill session '<code>{name}</code>'.", parse_mode=constants.ParseMode.HTML)

async def show_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /log <n>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    lines = 20
    if context.args:
        try:
            lines = int(context.args[0])
        except ValueError:
            pass
    
    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)
        
        if not user_data.active_session_id:
            await update.message.reply_text("⚠️ No active session selected.")
            return
        
        from sqlalchemy import select
        from stayssh.db.models import Session
        stmt = select(Session.name).where(Session.id == user_data.active_session_id)
        result = await db.execute(stmt)
        session_name = result.scalar_one_or_none()
        
        if not session_name:
            await update.message.reply_text("❌ Selected session not found.")
            return

        log = await tmux_manager.get_history(session_name, lines)
        if log:
            await update.message.reply_text(f"📋 <b>Last {lines} lines for {session_name}:</b>\n<code>{log}</code>", parse_mode=constants.ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Failed to retrieve log.")

async def manage_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /config [set <key> <value>]."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    if not context.args:
        # Show all settings
        async with async_session_factory() as db:
            repo = SettingRepository(db)
            all_settings = []
            for key in ["BATCH_INTERVAL_MS", "IDLE_THRESHOLD_MS", "LOG_LEVEL", "POLL_INTERVAL_MS"]:
                val = await repo.get_value(key) or getattr(settings, key)
                all_settings.append(f"• <code>{key}</code>: {val}")
            
            await update.message.reply_text(
                "⚙️ <b>Current Settings:</b>\n" + "\n".join(all_settings) + 
                "\n\nUse <code>/config set &lt;key&gt; &lt;value&gt;</code> to change.",
                parse_mode=constants.ParseMode.HTML
            )
            return

    if context.args[0] == "set" and len(context.args) >= 3:
        key, value = context.args[1], context.args[2]
        if not hasattr(settings, key):
            await update.message.reply_text(f"❌ Invalid setting key: <code>{key}</code>", parse_mode=constants.ParseMode.HTML)
            return
        
        async with async_session_factory() as db:
            repo = SettingRepository(db)
            await repo.set_value(key, value)
            await db.commit()
        
        # Update local settings object
        try:
            current_val = getattr(settings, key)
            setattr(settings, key, type(current_val)(value))
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to parse value: {e}")
            return
        
        # If logging level changed, re-setup logging
        if key == "LOG_LEVEL":
            setup_logging()
            
        await update.message.reply_text(f"✅ Setting <code>{key}</code> updated to <code>{value}</code>.", parse_mode=constants.ParseMode.HTML)
    else:
        await update.message.reply_text("⚠️ Usage: /config [set <key> <value>]")

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /restart."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    await update.message.reply_text("🔄 Restarting StaySSH Bot...")
    # Exit process; run_local.sh or Docker will restart it.
    os._exit(0)

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Passes messages as commands to the active tmux session."""
    user_id = update.effective_user.id
    if user_id != settings.ADMIN_USER_ID: return

    cmd = update.message.text
    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(user_id)
        
        if not user_data.active_session_id:
            await update.message.reply_text("⚠️ No active session selected. Use /switch <name> or /new <name>.")
            return
        
        from sqlalchemy import select
        from stayssh.db.models import Session
        stmt = select(Session.name).where(Session.id == user_data.active_session_id)
        result = await db.execute(stmt)
        session_name = result.scalar_one_or_none()
        
        if not session_name:
            await update.message.reply_text("❌ Selected session not found or inactive.")
            return

        success = await tmux_manager.send_keys(session_name, cmd)
        if not success:
            await update.message.reply_text("❌ Failed to send command to host.")

async def output_monitor_task(application) -> None:
    """Background task to poll tmux output and feed the batcher."""
    logger.info("Starting output monitor task...")
    session_line_counts = {}

    while True:
        try:
            async with async_session_factory() as db:
                session_repo = SessionRepository(db)
                active_sessions = await session_repo.get_active_sessions()
            
            for session in active_sessions:
                output_dto = await tmux_manager.capture_pane(session.name)
                if not output_dto:
                    continue
                
                last_count = session_line_counts.get(session.name, 0)
                lines = output_dto.content.splitlines()
                new_count = len(lines)
                
                if new_count > last_count:
                    new_lines = lines[last_count:]
                    new_text = "\n".join(new_lines)
                    await batcher.add_message(session.name, new_text)
                
                session_line_counts[session.name] = new_count
                
        except Exception as e:
            logger.error(f"Error in output monitor: {e}")
            
        await asyncio.sleep(settings.POLL_INTERVAL_MS / 1000.0)

async def main() -> None:
    global batcher
    
    # Initialize Bot
    application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()
    
    # Initialize Batcher
    async def telegram_sender(text: str):
        await application.bot.send_message(chat_id=settings.ADMIN_USER_ID, text=text, parse_mode=constants.ParseMode.HTML)
    batcher = AdaptiveBatcher(telegram_sender)

    # Startup Sync
    async with async_session_factory() as db:
        session_repo = SessionRepository(db)
        sync_service = SyncService(session_repo, tmux_manager)
        await sync_service.sync_on_startup(settings.ADMIN_USER_ID)
        await db.commit()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sessions", list_sessions))
    application.add_handler(CommandHandler("new", create_session))
    application.add_handler(CommandHandler("switch", switch_session))
    application.add_handler(CommandHandler("kill", kill_session))
    application.add_handler(CommandHandler("log", show_log))
    application.add_handler(CommandHandler("config", manage_config))
    application.add_handler(CommandHandler("restart", restart_bot))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_command))

    # Background Tasks
    asyncio.create_task(output_monitor_task(application))

    logger.info("StaySSH Bot is running.")
    await application.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("StaySSH Bot stopped by user.")
