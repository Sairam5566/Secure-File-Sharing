"""
Database Models
Defines SQLAlchemy ORM models with patent-grade features:
- User: RBAC with role field
- File: Blockchain-ready hash + soft delete
- AccessLog: ML-ready logging with IP, device, action type
"""
from datetime import datetime as _datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index, Float
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """
    User model with Role-Based Access Control (RBAC)
    """
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")  # user, admin, auditor
    created_at: Mapped[_datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    files: Mapped[List["File"]] = relationship("File", back_populates="owner", cascade="all, delete-orphan")
    access_logs: Mapped[List["AccessLog"]] = relationship("AccessLog", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class File(Base):
    """
    File model with blockchain-ready hashing and soft delete
    """
    __tablename__ = "files"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256 hash for blockchain anchoring
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    upload_time: Mapped[_datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Soft delete for audit compliance
    blockchain_tx_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)  # Store blockchain transaction hash
    blockchain_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Store index in blockchain registry
    
    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="files")
    access_logs: Mapped[List["AccessLog"]] = relationship("AccessLog", back_populates="file", cascade="all, delete-orphan")
    
    # Index for efficient queries
    __table_args__ = (
        Index('ix_files_owner_not_deleted', 'owner_id', 'is_deleted'),
    )
    
    def __repr__(self):
        return f"<File(id={self.id}, filename='{self.filename}', hash='{self.file_hash[:8]}...', deleted={self.is_deleted})>"


class AccessLog(Base):
    """
    Access log model with ML-ready fields for anomaly detection
    Captures IP address, device info, and action type
    """
    __tablename__ = "access_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    file_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("files.id"), nullable=True)  # Nullable for failed access attempts / logins
    access_time: Mapped[_datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    access_status: Mapped[str] = mapped_column(String(20), nullable=False)  # granted, denied
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv4 or IPv6
    device_info: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # User-Agent string
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)  # upload, download, delete
    is_anomalous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    anomaly_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="access_logs")
    file: Mapped[Optional["File"]] = relationship("File", back_populates="access_logs")
    
    # Composite index for ML queries (user activity over time)
    __table_args__ = (
        Index('ix_access_logs_user_time', 'user_id', 'access_time'),
        Index('ix_access_logs_action_time', 'action_type', 'access_time'),
    )
    
    def __repr__(self):
        return f"<AccessLog(id={self.id}, user_id={self.user_id}, action='{self.action_type}', status='{self.access_status}')>"
