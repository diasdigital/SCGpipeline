from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base

class User(Base):
    """
    System users table.

    The role field distinguishes two account types:
        - 'user'      : Research participants using the chat interface.
        - 'developer' : Researchers who can create new accounts and monitor MLflow.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    rooms = relationship("ChatRoom", back_populates="user", cascade="all, delete-orphan")
    
class ChatRoom(Base):
    """
    Chat room table.

    Each user can have multiple rooms to separate conversation topics.
    Rooms are auto-named from the first 30 characters of the first prompt.
    """
    __tablename__ = "chat_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), default="New Conversation")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Soft Delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    user = relationship("User", back_populates="rooms")
    chats = relationship("ChatLog", back_populates="room", cascade="all, delete-orphan")
    
class ChatLog(Base):
    """
    Chat log table — the most important table in this system.

    Each row represents one question-answer pair between a user and the LLM,
    along with the hallucination evaluation results run in the background by Celery.
    """
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    llm_response: Mapped[str] = mapped_column(Text, nullable=False)

    is_evaluating: Mapped[bool] = mapped_column(default=True)

    hallucination_score: Mapped[float] = mapped_column(Float, nullable=True)
    evaluation_method = Column(String(20), default="nli")
    user_feedback: Mapped[int] = mapped_column(Integer, nullable=True)

    llm_model         = Column(String(100), nullable=True)   # e.g. "gemini-3.1-flash-lite"
    llm_provider      = Column(String(30),  nullable=True)   # e.g. "gemini"
    temperature_sample = Column(Float,       nullable=True)  # e.g. 1.0
    num_samples        = Column(Integer,     nullable=True)  # e.g. 5
    
    time_sampling_sec = Column(Float, nullable=True)
    time_evaluation_sec = Column(Float, nullable=True)
    total_process_sec = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    room = relationship("ChatRoom", back_populates="chats")