import os
import shutil
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional

import models, schemas
from database import engine, get_db
from dependencies import get_current_user, require_admin

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ProjectFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows any frontend URL to connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/avatars", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root(): return {"message": "ProjectFlow API is running successfully"}

# --- USER ROUTES ---
@app.get("/users/me", response_model=schemas.UserResponse)
def get_my_profile(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.get("/users", response_model=List[schemas.UserResponse])
def search_users(search: Optional[str] = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.User)
    if search:
        search_term = f"%{search}%"
        query = query.filter(models.User.username.ilike(search_term))
    query = query.filter(models.User.id != current_user.id)
    return query.all()

@app.put("/users/me/username", response_model=schemas.UserResponse)
def update_username(update_data: schemas.UsernameUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    existing_user = db.query(models.User).filter(models.User.username == update_data.username).first()
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=400, detail="This username is already taken.")
    current_user.username = update_data.username
    db.commit()
    db.refresh(current_user)
    return current_user

@app.get("/users/resolve/{username}")
def resolve_username_to_email(username: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user: raise HTTPException(status_code=404, detail="Username not found.")
    return {"email": user.email}

@app.post("/users/me/avatar")
async def upload_avatar(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)):
    if not file.content_type.startswith("image/"): raise HTTPException(status_code=400, detail="File must be an image")
    file_extension = file.filename.split(".")[-1]
    filename = f"{current_user.id}.{file_extension}"
    with open(f"static/avatars/{filename}", "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"avatar_url": f"http://localhost:8000/static/avatars/{filename}", "message": "Avatar updated"}


# --- GROUPS ROUTES (NEW) ---
@app.post("/groups", response_model=schemas.GroupResponse)
def create_group(group: schemas.GroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Creates a new group and automatically adds the creator as a member."""
    new_group = models.Group(name=group.name, password=group.password, owner_id=current_user.id)
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    
    # Add creator as the first member
    member = models.GroupMember(group_id=new_group.id, user_id=current_user.id)
    db.add(member)
    db.commit()
    return new_group

@app.post("/groups/join")
def join_group(group_data: schemas.GroupJoin, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Join an existing group using its ID and Password."""
    group = db.query(models.Group).filter(models.Group.id == group_data.group_id).first()
    if not group: 
        raise HTTPException(status_code=404, detail="Group not found. Check the ID.")
    if group.password != group_data.password: 
        raise HTTPException(status_code=400, detail="Incorrect group password.")
    
    existing = db.query(models.GroupMember).filter(models.GroupMember.group_id == group.id, models.GroupMember.user_id == current_user.id).first()
    if existing: 
        raise HTTPException(status_code=400, detail="You are already a member of this group.")
    
    member = models.GroupMember(group_id=group.id, user_id=current_user.id)
    db.add(member)
    db.commit()
    return {"message": f"Successfully joined {group.name}!"}

@app.get("/groups", response_model=List[schemas.GroupResponse])
def get_my_groups(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Get all groups the current user is a part of."""
    memberships = db.query(models.GroupMember).filter(models.GroupMember.user_id == current_user.id).all()
    group_ids = [m.group_id for m in memberships]
    return db.query(models.Group).filter(models.Group.id.in_(group_ids)).all()
# ---------------------------

# --- NOTIFICATIONS ---
@app.get("/notifications")
def get_notifications(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    pending = db.query(models.Connection).filter(models.Connection.receiver_id == current_user.id, models.Connection.status == models.ConnectionStatus.PENDING).all()
    requests = []
    for c in pending:
        req_user = db.query(models.User).filter(models.User.id == c.requester_id).first()
        requests.append({"connection_id": c.id, "user": {"id": req_user.id, "name": req_user.name, "username": req_user.username}})
    unread = db.query(models.Message).filter(models.Message.receiver_id == current_user.id, models.Message.is_read == False).all()
    messages = []
    for m in unread:
        sender = db.query(models.User).filter(models.User.id == m.sender_id).first()
        messages.append({"message_id": m.id, "sender_id": sender.id, "sender_name": sender.name, "content": m.content})
    return {"friend_requests": requests, "unread_messages": messages}

# --- MESSAGING ---
@app.post("/messages", response_model=schemas.MessageResponse)
def send_message(message: schemas.MessageCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_msg = models.Message(sender_id=current_user.id, receiver_id=message.receiver_id, content=message.content)
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    return new_msg

@app.get("/messages/{other_user_id}", response_model=List[schemas.MessageResponse])
def get_messages(other_user_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Message).filter(or_(and_(models.Message.sender_id == current_user.id, models.Message.receiver_id == other_user_id), and_(models.Message.sender_id == other_user_id, models.Message.receiver_id == current_user.id))).order_by(models.Message.timestamp.asc()).all()

@app.put("/messages/read/{sender_id}")
def mark_messages_read(sender_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    unread_msgs = db.query(models.Message).filter(models.Message.sender_id == sender_id, models.Message.receiver_id == current_user.id, models.Message.is_read == False).all()
    for msg in unread_msgs: msg.is_read = True
    db.commit()
    return {"status": "success"}

# --- DASHBOARD ---
@app.get("/dashboard/kpis")
def get_dashboard_metrics(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    now = datetime.utcnow()
    active_projects_count = db.query(models.Project).filter(models.Project.owner_id == current_user.id).count()
    pending_tasks_count = db.query(models.Task).filter(models.Task.assignee_id == current_user.id, models.Task.status != models.StatusEnum.DONE).count()
    overdue_tasks_count = db.query(models.Task).filter(models.Task.assignee_id == current_user.id, models.Task.status != models.StatusEnum.DONE, models.Task.due_date < now).count()
    return { "active_projects": active_projects_count, "pending_tasks": pending_tasks_count, "overdue_tasks": overdue_tasks_count }

# --- CONNECTIONS (FRIENDS) ---
@app.post("/connections", response_model=schemas.ConnectionResponse)
def send_friend_request(request: schemas.ConnectionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if request.receiver_id == current_user.id: raise HTTPException(status_code=400, detail="Cannot send a request to yourself.")
    receiver = db.query(models.User).filter(models.User.id == request.receiver_id).first()
    if not receiver: raise HTTPException(status_code=404, detail="User not found.")
    existing_connection = db.query(models.Connection).filter(or_(and_(models.Connection.requester_id == current_user.id, models.Connection.receiver_id == request.receiver_id), and_(models.Connection.requester_id == request.receiver_id, models.Connection.receiver_id == current_user.id))).first()
    if existing_connection: raise HTTPException(status_code=400, detail="Connection already exists or is pending.")
    new_connection = models.Connection(requester_id=current_user.id, receiver_id=request.receiver_id, status=models.ConnectionStatus.PENDING)
    db.add(new_connection)
    db.commit()
    db.refresh(new_connection)
    return new_connection

@app.put("/connections/{connection_id}/accept", response_model=schemas.ConnectionResponse)
def accept_friend_request(connection_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    connection = db.query(models.Connection).filter(models.Connection.id == connection_id).first()
    if not connection or connection.receiver_id != current_user.id: raise HTTPException(status_code=404, detail="Not authorized.")
    connection.status = models.ConnectionStatus.ACCEPTED
    db.commit()
    db.refresh(connection)
    return connection

@app.delete("/connections/{connection_id}")
def reject_friend_request(connection_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    connection = db.query(models.Connection).filter(models.Connection.id == connection_id).first()
    if not connection or connection.receiver_id != current_user.id: raise HTTPException(status_code=404, detail="Not authorized.")
    db.delete(connection)
    db.commit()
    return {"status": "success"}

@app.get("/connections/friends", response_model=List[schemas.FriendProfileResponse])
def get_my_friends(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    connections = db.query(models.Connection).filter(and_(models.Connection.status == models.ConnectionStatus.ACCEPTED, or_(models.Connection.requester_id == current_user.id, models.Connection.receiver_id == current_user.id))).all()
    friends_list = []
    for conn in connections:
        friend_id = conn.receiver_id if conn.requester_id == current_user.id else conn.requester_id
        friend_user = db.query(models.User).filter(models.User.id == friend_id).first()
        friends_list.append({"connection_id": conn.id, "user": friend_user})
    return friends_list

# --- PROJECT & TASK ROUTES ---
@app.get("/projects", response_model=List[schemas.ProjectResponse])
def get_all_projects(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Project).all()

@app.post("/projects", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(require_admin)):
    new_project = models.Project(**project.model_dump(), owner_id=admin_user.id)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project

@app.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(require_admin)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return None

@app.get("/tasks", response_model=List[schemas.TaskResponse])
def get_my_tasks(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Task).filter(models.Task.assignee_id == current_user.id).all()

@app.post("/projects/{project_id}/tasks", response_model=schemas.TaskResponse)
def create_task(project_id: int, task: schemas.TaskCreate, db: Session = Depends(get_db), admin_user: models.User = Depends(require_admin)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    new_task = models.Task(**task.model_dump(), project_id=project_id)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@app.put("/tasks/{task_id}/status", response_model=schemas.TaskResponse)
def update_task_status(task_id: int, task_update: schemas.TaskUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: raise HTTPException(status_code=404, detail="Task not found")
    task.status = task_update.status
    db.commit()
    db.refresh(task)
    return task

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db), admin_user: models.User = Depends(require_admin)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return None