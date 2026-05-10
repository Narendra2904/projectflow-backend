from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models import RoleEnum, StatusEnum, ConnectionStatus

class UserResponse(BaseModel):
    id: str
    email: str
    username: Optional[str]
    name: str
    role: RoleEnum
    class Config: from_attributes = True

class UsernameUpdate(BaseModel):
    username: str

# --- NEW: GROUP SCHEMAS ---
class GroupCreate(BaseModel):
    name: str
    password: str

class GroupJoin(BaseModel):
    group_id: int
    password: str

class GroupResponse(BaseModel):
    id: int
    name: str
    owner_id: str
    class Config: from_attributes = True
# --------------------------

class ConnectionCreate(BaseModel):
    receiver_id: str

class ConnectionResponse(BaseModel):
    id: int
    requester_id: str
    receiver_id: str
    status: ConnectionStatus
    class Config: from_attributes = True

class FriendProfileResponse(BaseModel):
    connection_id: int
    user: UserResponse

class MessageCreate(BaseModel):
    receiver_id: str
    content: str

class MessageResponse(BaseModel):
    id: int
    sender_id: str
    receiver_id: str
    content: str
    timestamp: datetime
    is_read: bool 
    class Config: from_attributes = True

class TaskCreate(BaseModel):
    title: str
    assignee_id: Optional[str] = None
    due_date: Optional[datetime] = None

class TaskUpdate(BaseModel):
    status: StatusEnum

class TaskResponse(BaseModel):
    id: int
    title: str
    status: StatusEnum
    due_date: Optional[datetime]
    project_id: int
    assignee_id: Optional[str] = None
    class Config: from_attributes = True

class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    owner_id: str
    tasks: List[TaskResponse] = []
    class Config: from_attributes = True