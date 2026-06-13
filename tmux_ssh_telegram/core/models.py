from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict

class SessionStatus(str, Enum):
    ACTIVE = "active"
    DETACHED = "detached"
    DEAD = "dead"

class SessionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    status: SessionStatus
    creator_id: int
    last_activity: datetime
    created_at: datetime

class TmuxOutputDTO(BaseModel):
    session_name: str
    content: str
    line_count: int
    is_truncated: bool = False

class CommandResultDTO(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration: float
