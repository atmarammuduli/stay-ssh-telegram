import asyncio
import asyncpg
from tmux_ssh_telegram.core.config import settings
from sqlalchemy import make_url

async def create_db():
    url = make_url(settings.DATABASE_URL)
    db_name = url.database
    host = "127.0.0.1" if url.host == "localhost" else url.host
    
    print(f"Connecting to {host}:{url.port or 5432} as {url.username} to create database '{db_name}'...")
    try:
        # Connect using individual parameters to avoid URL encoding issues
        conn = await asyncpg.connect(
            user=url.username,
            password=url.password,
            host=host,
            port=url.port or 5432,
            database="postgres"
        )
        try:
            # Check if exists
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
            if not exists:
                # We need to use a separate connection for CREATE DATABASE as it cannot run in a transaction block
                # but asyncpg.connect() doesn't start a transaction by default.
                # However, CREATE DATABASE cannot be run with other commands.
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                print(f"✅ Database '{db_name}' created.")
            else:
                print(f"ℹ️ Database '{db_name}' already exists.")
        finally:
            await conn.close()
    except Exception as e:
        print(f"❌ Failed to create database: {e}")

if __name__ == "__main__":
    asyncio.run(create_db())
