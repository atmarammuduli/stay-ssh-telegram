import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import sys

async def check_db():
    # Password: P9$tg5%s@3r$t
    # Encoded: P9%24tg5%25s%403r%24t
    url = "postgresql+asyncpg://postgres:P9%24tg5%25s%403r%24t@localhost:5432/tmux-ssh-telegram"
    try:
        engine = create_async_engine(url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ Postgres is accessible")
        await engine.dispose()
    except Exception as e:
        print(f"❌ Postgres connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(check_db())
