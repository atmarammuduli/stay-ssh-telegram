import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from stayssh.db.models import Base, User, Session
from stayssh.db.repositories import UserRepository, SessionRepository
from stayssh.core.config import settings
import os

# Integration tests require a running database.
# We skip them if DATABASE_URL is not set or points to localhost but no DB is there.
DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION", "false").lower() == "true"

@pytest.mark.skipif(not RUN_INTEGRATION, reason="RUN_INTEGRATION=true not set")
class TestDatabaseIntegration:
    @pytest_asyncio.fixture(autouse=True)
    async def setup_db(self):
        engine = create_async_engine(DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        self.session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Clean data before test
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE users, sessions, settings CASCADE"))
        
        yield
        
        # Clean data after test
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE users, sessions, settings CASCADE"))
        
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_user_session_workflow(self):
        async with self.session_factory() as db:
            user_repo = UserRepository(db)
            session_repo = SessionRepository(db)
            
            # 1. Create User
            user = await user_repo.get_or_create(12345, is_admin=True)
            await db.commit()
            assert user.id == 12345
            
            # 2. Create Session
            session_dto = await session_repo.create("test_session", user.id)
            await db.commit()
            assert session_dto.name == "test_session"
            
            # 3. Set Active Session
            await user_repo.set_active_session(user.id, session_dto.id)
            await db.commit()
            
            # 4. Verify
            user_updated = await user_repo.get_or_create(12345)
            assert user_updated.active_session_id == session_dto.id
