"""
app/schemas/api_schemas.py
==========================
Pydantic schemas untuk request dan response API.

Validasi terjadi secara otomatis saat FastAPI menerima request.
Jika data tidak valid, FastAPI langsung mengembalikan 422 Unprocessable Entity
beserta detail field mana yang bermasalah — tanpa perlu if/else manual.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    username: str
    role: str = "user"


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# ROOM
# ─────────────────────────────────────────────────────────────────────────────

class RoomCreate(BaseModel):
    room_name: str = Field(
        default="New Conversation",
        min_length=1,
        max_length=100,
        description="Nama room, maks 100 karakter",
    )


class RoomResponse(BaseModel):
    id: int
    user_id: int
    room_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class RoomUpdate(BaseModel):
    room_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nama room baru, maks 100 karakter",
    )


# ─────────────────────────────────────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────────────────────────────────────

class ChatLogCreate(BaseModel):
    room_id: int = Field(
        ...,
        gt=0,
        description="ID room tujuan, harus > 0",
    )
    prompt_text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Teks prompt, 1–5000 karakter",
    )

    @field_validator("prompt_text")
    @classmethod
    def strip_and_reject_blank(cls, v: str) -> str:
        """
        Hapus whitespace di awal/akhir, lalu tolak jika hasilnya kosong.
        Mencegah prompt seperti "   " (spasi saja) lolos validasi min_length.
        """
        stripped = v.strip()
        if not stripped:
            raise ValueError("Prompt tidak boleh hanya berisi spasi atau baris kosong.")
        return stripped


class ChatLogResponse(BaseModel):
    id: int
    room_id: int
    prompt_text: str
    llm_response: str
    is_evaluating: bool
    hallucination_score: Optional[float] = None
    evaluation_method: str
    user_feedback: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatFeedbackUpdate(BaseModel):
    user_feedback: int = Field(
        ...,
        description="Rating: 1 = faktual (jempol atas), -1 = halusinasi (jempol bawah)",
    )

    @field_validator("user_feedback")
    @classmethod
    def must_be_valid_rating(cls, v: int) -> int:
        if v not in (1, -1):
            raise ValueError("user_feedback harus 1 (faktual) atau -1 (halusinasi).")
        return v