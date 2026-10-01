"""
Pydantic Schemas
Request/response validation models with enhanced fields
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from datetime import datetime
from typing import Optional


# ============================================================================
# User Schemas
# ============================================================================

class UserCreate(BaseModel):
    """Schema for user registration (role is always 'user' — use CLI for admin)"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if v and len(v.encode('utf-8')) > 72:
            raise ValueError("password_too_long")
        return v


class UserLogin(BaseModel):
    """Schema for user login"""
    username: str
    password: str


class UserResponse(BaseModel):
    """Schema for user response"""
    id: int
    username: str
    email: str
    role: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Token Schemas
# ============================================================================

class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for JWT token payload"""
    username: Optional[str] = None
    role: Optional[str] = None


# ============================================================================
# File Schemas
# ============================================================================

class FileUpload(BaseModel):
    """Schema for file upload metadata"""
    filename: str


class FileResponse(BaseModel):
    """Schema for file response"""
    id: int
    filename: str
    file_hash: str
    owner_id: int
    upload_time: datetime
    is_deleted: bool
    blockchain_tx_hash: Optional[str] = None
    blockchain_index: Optional[int] = None
    is_anomalous: Optional[bool] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Access Log Schemas
# ============================================================================

class AccessLogResponse(BaseModel):
    """Schema for access log response"""
    id: int
    user_id: int
    file_id: Optional[int]
    access_time: datetime
    access_status: str
    ip_address: Optional[str]
    device_info: Optional[str]
    action_type: str
    is_anomalous: bool
    anomaly_score: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Error Response Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    """Schema for consistent error responses"""
    detail: str
    error_code: Optional[str] = None


class ValidationErrorResponse(BaseModel):
    """Schema for validation error responses"""
    detail: str
    errors: list
