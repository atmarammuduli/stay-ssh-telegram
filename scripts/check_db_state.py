import asyncio
from sqlalchemy import select
from tmux_ssh_telegram.db.connection import async_session_factory
from tmux_ssh_telegram.db.models import User, Session
from tmux_ssh_telegram.core.config import settings

async def check_state():
    async with async_session_factory() as db:
        # Check admin user
        stmt = select(User).where(User.id == settings.ADMIN_USER_ID)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            print(f"User {user.id}: active_session_id={user.active_session_id}")
            if user.active_session_id:
                stmt = select(Session).where(Session.id == user.active_session_id)
                result = await db.execute(stmt)
                session = result.scalar_one_or_none()
                if session:
                    print(f"Active Session Name: {session.name}")
                else:
                    print("Active Session ID points to non-existent session!")
        else:
            print(f"Admin user {settings.ADMIN_USER_ID} not found in DB!")

        # List all sessions
        stmt = select(Session)
        result = await db.execute(stmt)
        sessions = result.scalars().all()
        print("\nAll Sessions in DB:")
        for s in sessions:
            print(f"- ID: {s.id}, Name: {s.name}, Active: {s.is_active}")

if __name__ == "__main__":
    asyncio.run(check_state())
