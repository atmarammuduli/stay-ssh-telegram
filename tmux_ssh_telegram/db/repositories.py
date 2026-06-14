from datetime import datetime
from typing import List, Optional, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tmux_ssh_telegram.db.models import User, Session, Setting
from tmux_ssh_telegram.core.models import SessionDTO, SessionStatus

class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_name(self, name: str) -> Optional[SessionDTO]:
        stmt = select(Session).where(Session.name == name)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        return SessionDTO.model_validate(session) if session else None

    async def get_active_sessions(self) -> List[SessionDTO]:
        stmt = select(Session).where(Session.status == SessionStatus.ACTIVE)
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        return [SessionDTO.model_validate(s) for s in sessions]

    async def get_all(self) -> List[SessionDTO]:
        stmt = select(Session)
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        return [SessionDTO.model_validate(s) for s in sessions]

    async def create(self, name: str, creator_id: int, description: Optional[str] = None) -> SessionDTO:
        session = Session(
            name=name,
            creator_id=creator_id,
            description=description,
            status=SessionStatus.ACTIVE,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        self.db.add(session)
        await self.db.flush()
        # In case of tests or no real DB, ensure id is set for DTO validation
        if session.id is None: session.id = 0 
        return SessionDTO.model_validate(session)

    async def update_status(self, session_id: int, status: SessionStatus) -> None:
        stmt = update(Session).where(Session.id == session_id).values(status=status, last_activity=datetime.utcnow())
        await self.db.execute(stmt)

class SettingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_value(self, key: str) -> Optional[str]:
        stmt = select(Setting.value).where(Setting.key == key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_value(self, key: str, value: str) -> None:
        # Simple upsert logic
        stmt = select(Setting).where(Setting.key == key)
        result = await self.db.execute(stmt)
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = Setting(key=key, value=value, updated_at=datetime.utcnow())
            self.db.add(setting)

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, user_id: int, is_admin: bool = False) -> User:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(id=user_id, is_admin=is_admin, created_at=datetime.utcnow())
            self.db.add(user)
            await self.db.flush()
        return user

    async def set_active_session(self, user_id: int, session_id: Optional[int]) -> None:
        stmt = update(User).where(User.id == user_id).values(active_session_id=session_id)
        await self.db.execute(stmt)
