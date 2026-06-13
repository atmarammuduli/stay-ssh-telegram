import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from tmux_ssh_telegram.core.config import settings
from tmux_ssh_telegram.core.models import SessionStatus
from tmux_ssh_telegram.db.connection import async_session_factory
from tmux_ssh_telegram.db.repositories import SessionRepository, UserRepository, SettingRepository
from tmux_ssh_telegram.ssh.manager import SSHManager
from tmux_ssh_telegram.ssh.tmux import TmuxManager
from tmux_ssh_telegram.bot.sync import SyncService
from tmux_ssh_telegram.bot.batcher import AdaptiveBatcher

# Logging Setup
def setup_logging() -> None:
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_file = os.path.join(settings.LOG_DIR, "tmux_ssh_telegram.log")
    
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

HELP_TEXT = (
    "👋 <b>StaySSH Bot Help</b>\n\n"
    "<b>Core Commands:</b>\n"
    "• /new | /n &lt;name&gt; - Create &amp; select a new session\n"
    "• /sessions | /ls - List sessions (with interactive buttons)\n"
    "• /switch | /sw &lt;name&gt; - Switch active session context\n"
    "• /kill | /k &lt;name&gt; - Force kill a session &amp; its processes\n"
    "• /status | /s - Show active session &amp; connection info\n"
    "• /screenshot | /ss [name] - View full-screen terminal snapshot\n\n"
    "<b>Terminal Interaction:</b>\n"
    "• <code>&lt;Any Text&gt;</code> - Sends text + Enter (C-m)\n"
    "• /type | /t &lt;text&gt; - Sends raw text <b>without</b> Enter\n"
    "• /key | /ky &lt;k&gt; - Send a special key or sequence\n"
    "  <i>Common:</i> <code>Escape</code>, <code>Tab</code>, <code>Up</code>, <code>Down</code>, <code>C-c</code>, <code>C-d</code>\n"
    "• /log | /l &lt;n&gt; - View last N lines of history\n\n"
    "<b>Bot Admin:</b>\n"
    "• /config | /c - View or update internal settings\n"
    "• /restart | /r - Hard restart the bot process\n\n"
    "📖 <i>Interactive Guide (nano, vim, gemini):</i>\n"
    "https://github.com/youruser/stay-ssh-telegram#interactive-usage-guide"
)

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

    await update.message.reply_text(HELP_TEXT, parse_mode=constants.ParseMode.HTML)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles unrecognized commands."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    await update.message.reply_text(
        "❓ <b>Unrecognized command.</b>\n\n" + HELP_TEXT,
        parse_mode=constants.ParseMode.HTML
    )

async def send_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /key <key>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /key <key_name> (e.g. Escape, C-c, Up)")
        return
    
    key = context.args[0]
    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)
        if not user_data.active_session_id:
            await update.message.reply_text("⚠️ No active session.")
            return
            
        from sqlalchemy import select
        from tmux_ssh_telegram.db.models import Session
        stmt = select(Session.name).where(Session.id == user_data.active_session_id)
        result = await db.execute(stmt)
        session_name = result.scalar_one_or_none()
        
        if session_name:
            success, error = await tmux_manager.send_raw_key(session_name, key)
            if not success:
                await update.message.reply_text(f"❌ <b>Key Send Failed:</b>\n<code>{error}</code>", parse_mode=constants.ParseMode.HTML)

async def type_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /type <text>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /type <text>")
        return
    
    text = " ".join(context.args)
    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)
        if not user_data.active_session_id:
            await update.message.reply_text("⚠️ No active session.")
            return
            
        from sqlalchemy import select
        from tmux_ssh_telegram.db.models import Session
        stmt = select(Session.name).where(Session.id == user_data.active_session_id)
        result = await db.execute(stmt)
        session_name = result.scalar_one_or_none()
        
        if session_name:
            success, error = await tmux_manager.send_keys(session_name, text, enter=False)
            if not success:
                await update.message.reply_text(f"❌ <b>Type Failed:</b>\n<code>{error}</code>", parse_mode=constants.ParseMode.HTML)

async def list_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /sessions with interactive buttons."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    names = await tmux_manager.list_sessions()
    if not names:
        await update.message.reply_text("ℹ️ No active tmux sessions found on host.")
        return
    
    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)
        active_id = user_data.active_session_id
        
        active_name = None
        if active_id:
            from sqlalchemy import select
            from tmux_ssh_telegram.db.models import Session
            stmt = select(Session.name).where(Session.id == active_id)
            result = await db.execute(stmt)
            active_name = result.scalar_one_or_none()

    keyboard = []
    for name in names:
        label = f"⭐ {name}" if name == active_name else name
        keyboard.append([InlineKeyboardButton(label, callback_data=f"switch:{name}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📂 <b>Active Host Sessions:</b>\nClick a button to switch context.",
        reply_markup=reply_markup,
        parse_mode=constants.ParseMode.HTML
    )

async def session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button clicks from /sessions."""
    query = update.callback_query
    if query.from_user.id != settings.ADMIN_USER_ID: return

    await query.answer()
    data = query.data
    
    if data.startswith("switch:"):
        name = data.split(":")[1]
        async with async_session_factory() as db:
            session_repo = SessionRepository(db)
            user_repo = UserRepository(db)
            session = await session_repo.get_by_name(name)
            
            if not session:
                # If not in DB, create it (sync with host)
                session = await session_repo.create(name, query.from_user.id)
            
            await user_repo.set_active_session(query.from_user.id, session.id)
            await db.commit()
        
        await query.edit_message_text(
            f"🎯 Switched to session '<code>{name}</code>'.",
            parse_mode=constants.ParseMode.HTML
        )

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

async def confirm_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /y to confirm a pending destructive action."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    pending = context.user_data.get("pending_command")
    if not pending:
        await update.message.reply_text("ℹ️ No pending action to confirm.")
        return
    
    cmd_type = pending.get("type")
    args = pending.get("args", [])
    
    # Clear pending immediately
    context.user_data["pending_command"] = None
    
    if cmd_type == "kill":
        name = args[0]
        success, error = await tmux_manager.kill_session(name)
        if success:
            async with async_session_factory() as db:
                session_repo = SessionRepository(db)
                session = await session_repo.get_by_name(name)
                if session:
                    await session_repo.update_status(session.id, SessionStatus.DEAD)
                    await db.commit()
            await update.message.reply_text(f"💀 Session '<code>{name}</code>' killed.", parse_mode=constants.ParseMode.HTML)
        else:
            await update.message.reply_text(f"❌ Failed to kill session: {error}")

    elif cmd_type == "restart":
        await update.message.reply_text("🔄 Restarting StaySSH Bot...")
        os._exit(0)

    elif cmd_type == "config":
        key, value = args[0], args[1]
        async with async_session_factory() as db:
            repo = SettingRepository(db)
            await repo.set_value(key, value)
            await db.commit()
        
        try:
            current_val = getattr(settings, key)
            setattr(settings, key, type(current_val)(value))
            if key == "LOG_LEVEL": setup_logging()
            await update.message.reply_text(f"✅ Setting <code>{key}</code> updated to <code>{value}</code>.", parse_mode=constants.ParseMode.HTML)
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to apply setting: {e}")

async def kill_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /kill <name> with confirmation."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /kill <name>")
        return
    
    name = context.args[0]
    context.user_data["pending_command"] = {"type": "kill", "args": [name]}
    await update.message.reply_text(
        f"❓ <b>Are you sure you want to kill session '<code>{name}</code>'?</b>\n"
        "This will terminate all processes in that session.\n\n"
        "Reply /y to confirm or any other command to cancel.",
        parse_mode=constants.ParseMode.HTML
    )

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
        from tmux_ssh_telegram.db.models import Session
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

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /status."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)
        
        session_name = "None"
        if user_data.active_session_id:
            from sqlalchemy import select
            from tmux_ssh_telegram.db.models import Session
            stmt = select(Session.name).where(Session.id == user_data.active_session_id)
            result = await db.execute(stmt)
            session_name = result.scalar_one_or_none() or "Unknown"

    connected = await ssh_manager.ensure_connected()
    conn_status = "✅ Connected" if connected else "❌ Disconnected"
    
    await update.message.reply_text(
        f"📊 <b>StaySSH Status:</b>\n"
        f"• <b>Connection:</b> {conn_status}\n"
        f"• <b>Host:</b> <code>{ssh_manager.host}</code>\n"
        f"• <b>Active Session:</b> <code>{session_name}</code>\n",
        parse_mode=constants.ParseMode.HTML
    )

async def show_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /screenshot [name]."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    session_name = None
    if context.args:
        session_name = context.args[0]
    else:
        async with async_session_factory() as db:
            user_repo = UserRepository(db)
            user_data = await user_repo.get_or_create(update.effective_user.id)
            if user_data.active_session_id:
                from sqlalchemy import select
                from tmux_ssh_telegram.db.models import Session
                stmt = select(Session.name).where(Session.id == user_data.active_session_id)
                result = await db.execute(stmt)
                session_name = result.scalar_one_or_none()
    
    if not session_name:
        await update.message.reply_text("⚠️ No active session and no session name provided.")
        return

    output_dto = await tmux_manager.capture_pane(session_name)
    if output_dto:
        await update.message.reply_text(
            f"📸 <b>Full Snapshot: {session_name}</b>\n<code>{output_dto.content}</code>",
            parse_mode=constants.ParseMode.HTML
        )
    else:
        await update.message.reply_text(f"❌ Failed to capture screenshot for session '<code>{session_name}</code>'.", parse_mode=constants.ParseMode.HTML)

async def manage_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /config [set <key> <value>] with confirmation."""
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
        
        context.user_data["pending_command"] = {"type": "config", "args": [key, value]}
        await update.message.reply_text(
            f"❓ <b>Are you sure you want to update <code>{key}</code> to <code>{value}</code>?</b>\n\n"
            "Reply /y to confirm.",
            parse_mode=constants.ParseMode.HTML
        )
    else:
        await update.message.reply_text("⚠️ Usage: /config [set <key> <value>]")

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /restart with confirmation."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    context.user_data["pending_command"] = {"type": "restart", "args": []}
    await update.message.reply_text(
        "❓ <b>Are you sure you want to restart the bot?</b>\n"
        "The bot will be offline for a few seconds.\n\n"
        "Reply /y to confirm.",
        parse_mode=constants.ParseMode.HTML
    )

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
        from tmux_ssh_telegram.db.models import Session
        stmt = select(Session.name).where(Session.id == user_data.active_session_id)
        result = await db.execute(stmt)
        session_name = result.scalar_one_or_none()
        
        if not session_name:
            await update.message.reply_text("❌ Selected session not found or inactive.")
            return

        success, error = await tmux_manager.send_keys(session_name, cmd)
        if not success:
            await update.message.reply_text(f"❌ <b>Command Failed:</b>\n<code>{error}</code>", parse_mode=constants.ParseMode.HTML)

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
                
                lines = output_dto.content.splitlines()
                new_count = len(lines)
                
                if session.name not in session_line_counts:
                    # Initial state: just track current count, don't dump history
                    logger.debug(f"Tracking session '{session.name}' starting at {new_count} lines.")
                    session_line_counts[session.name] = new_count
                    continue

                last_count = session_line_counts[session.name]
                
                if new_count > last_count:
                    new_lines = lines[last_count:]
                    new_text = "\n".join(new_lines)
                    await batcher.add_message(session.name, new_text)
                    session_line_counts[session.name] = new_count
                elif new_count < last_count:
                    # History probably cleared or reset
                    logger.debug(f"Session '{session.name}' line count reset ({last_count} -> {new_count}).")
                    session_line_counts[session.name] = new_count
                
        except Exception as e:
            logger.error(f"Error in output monitor: {e}")
            
        await asyncio.sleep(settings.POLL_INTERVAL_MS / 1000.0)

async def post_init(application) -> None:
    """Async initialization after the application is built."""
    global batcher
    
    # Initialize Batcher
    async def telegram_sender(text: str):
        await application.bot.send_message(chat_id=settings.ADMIN_USER_ID, text=text, parse_mode=constants.ParseMode.HTML)
    batcher = AdaptiveBatcher(telegram_sender)

    # Ensure Admin User Exists (to prevent FK errors during sync)
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

def main() -> None:
    # Initialize Bot
    application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).post_init(post_init).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("st", start))
    
    application.add_handler(CommandHandler("sessions", list_sessions))
    application.add_handler(CommandHandler("ls", list_sessions))
    
    application.add_handler(CommandHandler("new", create_session))
    application.add_handler(CommandHandler("n", create_session))
    
    application.add_handler(CommandHandler("switch", switch_session))
    application.add_handler(CommandHandler("sw", switch_session))
    
    application.add_handler(CommandHandler("kill", kill_session))
    application.add_handler(CommandHandler("k", kill_session))
    
    application.add_handler(CommandHandler("log", show_log))
    application.add_handler(CommandHandler("l", show_log))
    
    application.add_handler(CommandHandler("screenshot", show_screenshot))
    application.add_handler(CommandHandler("ss", show_screenshot))
    
    application.add_handler(CommandHandler("key", send_key))
    application.add_handler(CommandHandler("ky", send_key))
    
    application.add_handler(CommandHandler("type", type_text))
    application.add_handler(CommandHandler("t", type_text))
    
    application.add_handler(CommandHandler("config", manage_config))
    application.add_handler(CommandHandler("c", manage_config))
    
    application.add_handler(CommandHandler("status", show_status))
    application.add_handler(CommandHandler("s", show_status))
    
    application.add_handler(CommandHandler("restart", restart_bot))
    application.add_handler(CommandHandler("r", restart_bot))
    
    # Inline Callbacks
    application.add_handler(CallbackQueryHandler(session_callback))
    
    # Handle confirmation
    application.add_handler(CommandHandler("y", confirm_action))
    
    # Handle unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_command))

    logger.info("StaySSH Bot is starting...")
    application.run_polling()

if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except KeyboardInterrupt:
        logger.info("StaySSH Bot stopped by user.")
