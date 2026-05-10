from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime, Boolean
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
from database import Base

class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"

class StatusEnum(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"

class ConnectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"

class Connection(Base):
    __tablename__ = "connections"
    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(String, ForeignKey("users.id"))
    receiver_id = Column(String, ForeignKey("users.id"))
    status = Column(Enum(ConnectionStatus), default=ConnectionStatus.PENDING)
    
    requester = relationship("User", foreign_keys=[requester_id])
    receiver = relationship("User", foreign_keys=[receiver_id])

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True) 
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True, nullable=True) 
    name = Column(String)
    role = Column(Enum(RoleEnum), default=RoleEnum.MEMBER)
    
    projects = relationship("Project", back_populates="owner")
    tasks = relationship("Task", back_populates="assignee")
    sent_requests = relationship("Connection", foreign_keys="[Connection.requester_id]", back_populates="requester")
    received_requests = relationship("Connection", foreign_keys="[Connection.receiver_id]", back_populates="receiver")

# --- NEW: GROUPS TABLES ---
class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True) # This acts as the Group ID for joining
    name = Column(String, index=True)
    password = Column(String) # Required to join
    owner_id = Column(String, ForeignKey("users.id"))
    
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")

class GroupMember(Base):
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"))
    user_id = Column(String, ForeignKey("users.id"))
    
    group = relationship("Group", back_populates="members")
    user = relationship("User")

# --------------------------

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(String, ForeignKey("users.id"))
    receiver_id = Column(String, ForeignKey("users.id"))
    content = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False) 

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    owner_id = Column(String, ForeignKey("users.id"))
    
    owner = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    status = Column(Enum(StatusEnum), default=StatusEnum.TODO)
    due_date = Column(DateTime, nullable=True) 
    project_id = Column(Integer, ForeignKey("projects.id"))
    assignee_id = Column(String, ForeignKey("users.id"), nullable=True) 
    
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", back_populates="tasks")