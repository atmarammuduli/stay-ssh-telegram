import asyncio
import logging
from stayssh.db.connection import engine
from stayssh.db.models import Base

logger = logging.getLogger(__name__)

async def init_db() -> None:
    """Initialize the database by creating all tables."""
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        # For development, we create tables directly. 
        # In production, alembic migrations should be used.
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialization complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_db())
