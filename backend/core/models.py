from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime, JSON, Index, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid
from backend.core.database import Base

class SessionStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    question_sets = relationship("QuestionSet", back_populates="owner")
    sessions = relationship("GenerationSession", back_populates="user", foreign_keys="GenerationSession.user_id")
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    created_tasks = relationship("Task", back_populates="created_by", foreign_keys="Task.created_by_id")

class GenerationSession(Base):
    __tablename__ = "generation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic = Column(String, index=True)
    num_questions = Column(Integer)
    num_sets = Column(Integer)
    difficulty = Column(String)
    question_type = Column(String)
    status = Column(String, default=SessionStatus.PENDING.value, index=True)
    progress = Column(Integer, default=0)  # Percentage 0-100
    current_step = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)

    user = relationship("User", back_populates="sessions", foreign_keys=[user_id])
    question_sets = relationship("QuestionSet", back_populates="session")
    task = relationship("Task", back_populates="sessions")

    __table_args__ = (
        Index('idx_user_status', 'user_id', 'status'),
        Index('idx_status_started', 'status', 'started_at'),
    )

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    topic = Column(String, index=True)
    num_questions = Column(Integer, default=5)
    num_sets = Column(Integer, default=1)
    difficulty = Column(String, default="medium")
    question_type = Column(String, default="multiple_choice")
    user_context = Column(Text, nullable=True)
    status = Column(String, default=TaskStatus.PENDING.value, index=True)
    assignee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assignee_id])
    created_by = relationship("User", back_populates="created_tasks", foreign_keys=[created_by_id])
    sessions = relationship("GenerationSession", back_populates="task")

    __table_args__ = (
        Index('idx_assignee_status', 'assignee_id', 'status'),
        Index('idx_created_by', 'created_by_id', 'created_at'),
    )

class QuestionSet(Base):
    __tablename__ = "question_sets"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    difficulty = Column(String, index=True)
    question_type = Column(String, index=True)
    validation_text = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id = Column(Integer, ForeignKey("generation_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Analytics fields for scaling
    question_count = Column(Integer, default=0)
    is_archived = Column(Boolean, default=False, index=True)

    owner = relationship("User", back_populates="question_sets")
    session = relationship("GenerationSession", back_populates="question_sets")
    questions = relationship("Question", back_populates="question_set", cascade="all, delete-orphan")
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_owner_created', 'owner_id', 'created_at'),
        Index('idx_topic_difficulty', 'topic', 'difficulty'),
        Index('idx_owner_archived', 'owner_id', 'is_archived'),
    )

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text)
    options = Column(JSON)  # Stored as a list of strings
    answer = Column(String)
    explanation = Column(Text)
    question_set_id = Column(Integer, ForeignKey("question_sets.id", ondelete="CASCADE"), index=True)
    
    # Additional metadata for better querying
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    order_index = Column(Integer, default=0, index=True)  # For maintaining question order

    question_set = relationship("QuestionSet", back_populates="questions")
    
    __table_args__ = (
        Index('idx_set_order', 'question_set_id', 'order_index'),
    )
