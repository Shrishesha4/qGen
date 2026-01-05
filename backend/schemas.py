from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    is_admin: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserWithStats(User):
    total_generations: int = 0
    total_questions: int = 0
    active_sessions: int = 0
    pending_tasks: int = 0

# Session Schemas
class SessionBase(BaseModel):
    topic: str
    num_questions: int
    num_sets: int
    difficulty: str
    question_type: str

class SessionCreate(SessionBase):
    task_id: Optional[int] = None

class Session(SessionBase):
    id: int
    session_id: str
    user_id: int
    status: str
    progress: int
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    task_id: Optional[int] = None

    class Config:
        from_attributes = True

class SessionWithUser(Session):
    user_email: str

# Task Schemas
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    topic: str
    num_questions: int = 5
    num_sets: int = 1
    difficulty: str = "medium"
    question_type: str = "multiple_choice"
    user_context: Optional[str] = None
    due_date: Optional[datetime] = None

class TaskCreate(TaskBase):
    assignee_id: int

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    topic: Optional[str] = None
    num_questions: Optional[int] = None
    num_sets: Optional[int] = None
    difficulty: Optional[str] = None
    question_type: Optional[str] = None
    user_context: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None

class Task(TaskBase):
    id: int
    status: str
    assignee_id: int
    created_by_id: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TaskWithUsers(Task):
    assignee_email: str
    created_by_email: str

# Question Schemas
class QuestionBase(BaseModel):
    id: Optional[int] = None
    description: str
    options: List[str]
    answer: str
    explanation: Optional[str] = None
    order_index: Optional[int] = 0
    
    class Config:
        from_attributes = True

class QuestionSet(BaseModel):
    id: int
    topic: str
    difficulty: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    validation_text: Optional[str] = None
    question_count: Optional[int] = 0
    is_archived: Optional[bool] = False
    session_id: Optional[int] = None
    questions: List[QuestionBase] = []

    class Config:
        from_attributes = True

class QuestionSetWithOwner(QuestionSet):
    owner_id: int
    owner_email: str

class GenerationHistory(BaseModel):
    session_id: Optional[int] = None
    topic: str
    difficulty: str
    question_type: str
    created_at: datetime
    total_questions: int
    num_sets: int
    question_sets: List[QuestionSet] = []
    
    class Config:
        from_attributes = True

class GenerationHistoryWithOwner(GenerationHistory):
    owner_id: int
    owner_email: str

# Dashboard Stats
class AdminDashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_generations: int
    total_questions: int
    active_sessions: int
    pending_tasks: int

class UserDashboardStats(BaseModel):
    total_generations: int
    total_questions: int
    pending_tasks: int
    completed_tasks: int

class Token(BaseModel):
    access_token: str
    token_type: str
