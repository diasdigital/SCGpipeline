from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

class UserLogin(BaseModel):
    username:str
    password:str

class Token(BaseModel):
    access_token:str
    token_type: str = "bearer"
    
class UserCreateByDev(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, description="Minimal 6 characters")
    role: Optional[str] = Field(
        default="user",
    )
    
    @field_validator("role")
    @classmethod
    def must_be_valid_role(cls, v: str) -> str:
        if v not in ("user", "developer"):
            raise ValueError("Role must be 'user' or 'developer'")
        return v
    
class UserResponse(BaseModel):
    id:int
    username:str
    role:str
    created_at:datetime
    
    class Config:
        from_attributes = True