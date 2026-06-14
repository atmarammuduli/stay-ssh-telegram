import os
import asyncio
import logging
from typing import Optional
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from tmux_ssh_telegram.core.config import settings
from tmux_ssh_telegram.core.models import SessionStatus
from tmux_ssh_telegram.db.connection import async_session_factory
from tmux_ssh_telegram.db.repositories import SessionRepository, UserRepository, SettingRepository
from tmux_ssh_telegram.ssh.manager import SSHManager
from tmux_ssh_telegram.ssh.tmux import TmuxManager

logger = logging.getLogger(__name__)

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
    logger.info(f"Command /start received from user {user.id}")
    if user.id != settings.ADMIN_USER_ID:
        logger.warning(f"Unauthorized /start attempt from user {user.id}")
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

async def get_managers(context: ContextTypes.DEFAULT_TYPE):
    """Helper to get managers from bot_data."""
    return context.bot_data.get("tmux_manager"), context.bot_data.get("ssh_manager")

async def send_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /key <key>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /key <key_name> (e.g. Escape, C-c, Up)")
        return
    
    key = context.args[0]
    tmux_manager, _ = await get_managers(context)
    
    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)
        
        if not user_data.active_session_id:
            await update.message.reply_text("⚠️ No active session selected.")
            return

        from tmux_ssh_telegram.db.models import Session
        from sqlalchemy import select
        stmt = select(Session.name).where(Session.id == user_data.active_session_id)
        result = await db.execute(stmt)
        session_name = result.scalar_one_or_none()
        
        if not session_name:
            await update.message.reply_text("❌ Selected session not found.")
            return

        success, error = await tmux_manager.send_raw_key(session_name, key)
        if not success:
            await update.message.reply_text(f"❌ <b>Key Failed:</b>\n<code>{error}</code>", parse_mode=constants.ParseMode.HTML)

async def type_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /type <text> (sends text without Enter)."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /type <text>")
        return
    
    text = " ".join(context.args)
    tmux_manager, _ = await get_managers(context)

    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)
        
        if not user_data.active_session_id:
            await update.message.reply_text("⚠️ No active session selected.")
            return

        from tmux_ssh_telegram.db.models import Session
        from sqlalchemy import select
        stmt = select(Session.name).where(Session.id == user_data.active_session_id)
        result = await db.execute(stmt)
        session_name = result.scalar_one_or_none()

        success, error = await tmux_manager.send_keys(session_name, text, enter=False)
        if not success:
            await update.message.reply_text(f"❌ <b>Type Failed:</b>\n<code>{error}</code>", parse_mode=constants.ParseMode.HTML)

async def list_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all available sessions with buttons to switch."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return

    async with async_session_factory() as db:
        session_repo = SessionRepository(db)
        sessions = await session_repo.get_active_sessions()
        
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)

    if not sessions:
        await update.message.reply_text("📭 No active sessions. Use /new <name> to create one.")
        return

    keyboard = []
    for s in sessions:
        prefix = "✅ " if s.id == user_data.active_session_id else ""
        keyboard.append([InlineKeyboardButton(f"{prefix}{s.name} ({s.status.value})", callback_data=f"switch_{s.id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🖥️ <b>Available Sessions:</b>", reply_markup=reply_markup, parse_mode=constants.ParseMode.HTML)

async def session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline button clicks for session switching."""
    query = update.callback_query
    if query.from_user.id != settings.ADMIN_USER_ID:
        await query.answer("Unauthorized.", show_alert=True)
        return

    await query.answer()
    data = query.data
    if data.startswith("switch_"):
        session_id = int(data.split("_")[1])
        async with async_session_factory() as db:
            user_repo = UserRepository(db)
            await user_repo.set_active_session(query.from_user.id, session_id)
            
            from tmux_ssh_telegram.db.models import Session
            from sqlalchemy import select
            stmt = select(Session.name).where(Session.id == session_id)
            res = await db.execute(stmt)
            s_name = res.scalar_one_or_none()
            await db.commit()

        await query.edit_message_text(f"🎯 Switched to session: <b>{s_name}</b>", parse_mode=constants.ParseMode.HTML)

async def create_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /new <name>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /new <session_name>")
        return
    
    name = context.args[0]
    tmux_manager, _ = await get_managers(context)

    async with async_session_factory() as db:
        session_repo = SessionRepository(db)
        existing = await session_repo.get_by_name(name)
        if existing:
            await update.message.reply_text(f"⚠️ Session '<code>{name}</code>' already exists.", parse_mode=constants.ParseMode.HTML)
            return

        success, error = await tmux_manager.create_session(name)
        if not success:
            await update.message.reply_text(f"❌ <b>Creation Failed:</b>\n<code>{error}</code>", parse_mode=constants.ParseMode.HTML)
            return

        session = await session_repo.create(name, update.effective_user.id)
        user_repo = UserRepository(db)
        await user_repo.set_active_session(update.effective_user.id, session.id)
        await db.commit()

    await update.message.reply_text(f"🚀 Session '<b>{name}</b>' created and selected.", parse_mode=constants.ParseMode.HTML)

async def switch_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /switch <name>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    logger.info(f"Command /switch received with args: {context.args}")
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /switch <session_name>")
        return
    
    name = context.args[0]
    async with async_session_factory() as db:
        session_repo = SessionRepository(db)
        session = await session_repo.get_by_name(name)
        if not session:
            await update.message.reply_text(f"❌ Session '<code>{name}</code>' not found.", parse_mode=constants.ParseMode.HTML)
            return

        user_repo = UserRepository(db)
        await user_repo.set_active_session(update.effective_user.id, session.id)
        await db.commit()

    await update.message.reply_text(f"🎯 Switched to session: <b>{name}</b>", parse_mode=constants.ParseMode.HTML)

async def kill_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /kill <name> with confirmation."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /kill <session_name>")
        return
    
    name = context.args[0]
    context.user_data["pending_command"] = {"type": "kill", "args": [name]}
    await update.message.reply_text(
        f"❓ <b>Are you sure you want to KILL session '<code>{name}</code>'?</b>\n"
        "This will terminate all processes in that session.\n\n"
        "Reply /y to confirm.",
        parse_mode=constants.ParseMode.HTML
    )

async def confirm_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /y confirmation for sensitive commands."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    pending = context.user_data.get("pending_command")
    if not pending:
        await update.message.reply_text("🤷 No pending action to confirm.")
        return

    cmd_type = pending["type"]
    args = pending["args"]
    tmux_manager, _ = await get_managers(context)

    if cmd_type == "kill":
        name = args[0]
        async with async_session_factory() as db:
            session_repo = SessionRepository(db)
            session = await session_repo.get_by_name(name)
            
            success, error = await tmux_manager.kill_session(name)
            if success:
                if session:
                    await session_repo.update_status(session.id, SessionStatus.DEAD)
                await db.commit()
                await update.message.reply_text(f"💀 Session '<b>{name}</b>' killed.")
            else:
                await update.message.reply_text(f"❌ <b>Kill Failed:</b>\n<code>{error}</code>", parse_mode=constants.ParseMode.HTML)

    elif cmd_type == "restart":
        await update.message.reply_text("♻️ Restarting bot process...")
        # Give some time for the message to be sent
        await asyncio.sleep(1)
        os.execv(os.sys.executable, ['python'] + os.sys.argv)

    elif cmd_type == "config":
        key, value = args[0], args[1]
        async with async_session_factory() as db:
            repo = SettingRepository(db)
            await repo.set_value(key, value)
            await db.commit()
            
            # Update live settings if possible (simple reload for some)
            if hasattr(settings, key):
                try:
                    setattr(settings, key, type(getattr(settings, key))(value))
                except Exception: pass
            
            await update.message.reply_text(f"✅ Setting <code>{key}</code> updated to <code>{value}</code>.", parse_mode=constants.ParseMode.HTML)

    context.user_data["pending_command"] = None

async def show_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /log <n>."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    lines_count = int(context.args[0]) if context.args else 20
    tmux_manager, _ = await get_managers(context)

    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)
        
        if not user_data.active_session_id:
            await update.message.reply_text("⚠️ No active session selected.")
            return

        from tmux_ssh_telegram.db.models import Session
        from sqlalchemy import select
        stmt = select(Session.name).where(Session.id == user_data.active_session_id)
        result = await db.execute(stmt)
        session_name = result.scalar_one_or_none()

        history = await tmux_manager.get_history(session_name, lines=lines_count)
        if history:
            await update.message.reply_text(f"📖 <b>Last {lines_count} lines of '{session_name}':</b>\n<pre>{history}</pre>", parse_mode=constants.ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Failed to retrieve history.")

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /status."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    _, ssh_manager = await get_managers(context)

    async with async_session_factory() as db:
        user_repo = UserRepository(db)
        user_data = await user_repo.get_or_create(update.effective_user.id)
        
        active_name = "None"
        if user_data.active_session_id:
            from tmux_ssh_telegram.db.models import Session
            from sqlalchemy import select
            stmt = select(Session.name).where(Session.id == user_data.active_session_id)
            res = await db.execute(stmt)
            active_name = res.scalar_one_or_none() or "None"

        conn_status = "🟢 Connected" if ssh_manager.is_connected() else "🔴 Disconnected"
        
        await update.message.reply_text(
            f"ℹ️ <b>StaySSH Status:</b>\n\n"
            f"• <b>Host:</b> <code>{settings.HOST_SSH_URL}</code>\n"
            f"• <b>Connection:</b> {conn_status}\n"
            f"• <b>Active Session:</b> <code>{active_name}</code>\n"
            f"• <b>Batcher:</b> {settings.BATCH_INTERVAL_MS}ms interval",
            parse_mode=constants.ParseMode.HTML
        )

async def show_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /screenshot [name]."""
    if update.effective_user.id != settings.ADMIN_USER_ID: return
    
    tmux_manager, _ = await get_managers(context)
    session_name = context.args[0] if context.args else None
    
    async with async_session_factory() as db:
        if not session_name:
            user_repo = UserRepository(db)
            user_data = await user_repo.get_or_create(update.effective_user.id)
            if user_data.active_session_id:
                from tmux_ssh_telegram.db.models import Session
                from sqlalchemy import select
                stmt = select(Session.name).where(Session.id == user_data.active_session_id)
                res = await db.execute(stmt)
                session_name = res.scalar_one_or_none()

    if not session_name:
        await update.message.reply_text("⚠️ No session specified or selected.")
        return

    output = await tmux_manager.capture_pane(session_name)
    if output:
        await update.message.reply_text(f"📸 <b>Full Snapshot: '{session_name}'</b>\n<pre>{output.content}</pre>", parse_mode=constants.ParseMode.HTML)
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
    logger.info(f"Message received from {user_id}: '{cmd}'")
    tmux_manager, _ = await get_managers(context)

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
