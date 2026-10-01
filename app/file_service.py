"""
File Service Module
Business logic for file operations including encryption, hashing, and validation
Separates business logic from route handlers for better testability and maintainability
"""
import os
import uuid
import logging
from typing import Tuple, Optional
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app import models
from app.encryption import encryption_manager
from app.config import settings
from app.ml.anomaly_detector import anomaly_detector

logger = logging.getLogger(__name__)


class FileService:
    """Service class for file operations"""
    
    @staticmethod
    def process_upload(file_content: bytes, filename: str, owner_id: int, db: Session) -> models.File:
        """
        Process file upload: hash, encrypt, save, and create database record
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            owner_id: ID of the file owner
            db: Database session
            
        Returns:
            File model instance
            
        Raises:
            HTTPException: If file processing fails
        """
        try:
            # Generate SHA-256 hash (blockchain-ready)
            file_hash = encryption_manager.generate_file_hash(file_content)
            
            # Encrypt file content
            encrypted_content = encryption_manager.encrypt_file(file_content)
            
            # Generate unique filename for encrypted file
            unique_filename = f"{uuid.uuid4()}_{filename}"
            encrypted_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
            
            # Ensure upload directory exists
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            
            # Save encrypted file
            with open(encrypted_path, "wb") as f:
                f.write(encrypted_content)
            
            # Create file record in database
            db_file = models.File(
                filename=filename,
                encrypted_path=encrypted_path,
                file_hash=file_hash,
                owner_id=owner_id
            )
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
            
            return db_file
            
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File upload failed"
            )
    
    @staticmethod
    def process_download(db_file: models.File, verify_hash: bool = True) -> Tuple[bytes, str]:
        """
        Process file download: decrypt and optionally verify hash
        
        Args:
            db_file: File model instance
            verify_hash: Whether to verify file hash integrity
            
        Returns:
            Tuple of (decrypted_content, filename)
            
        Raises:
            HTTPException: If file not found, decryption fails, or hash mismatch
        """
        try:
            # Check if file exists on disk
            if not os.path.exists(str(db_file.encrypted_path)):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found on disk"
                )
            
            # Read encrypted file
            with open(str(db_file.encrypted_path), "rb") as f:
                encrypted_content = f.read()
            
            # Decrypt file
            decrypted_content = encryption_manager.decrypt_file(encrypted_content)
            
            # Verify hash integrity if requested
            if verify_hash:
                current_hash = encryption_manager.generate_file_hash(decrypted_content)
                if current_hash != db_file.file_hash:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="File integrity check failed: hash mismatch"
                    )
            
            return decrypted_content, db_file.filename
            
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File download failed"
            )
    
    @staticmethod
    def verify_file_access(db_file: models.File, user: models.User) -> bool:
        """
        Verify if user has access to the file
        
        Args:
            db_file: File model instance
            user: User model instance
            
        Returns:
            has_access: bool
        """
        # Owner has access
        if db_file.owner_id == user.id:
            return True
        
        # Admin and auditor have access to all files
        if user.role in ["admin", "auditor"]:
            return True
        
        return False
    
    @staticmethod
    def verify_file_delete_access(db_file: models.File, user: models.User) -> bool:
        """
        Verify if user has permission to delete the file
        
        Args:
            db_file: File model instance
            user: User model instance
            
        Returns:
            True if user can delete, False otherwise
        """
        # Owner can delete
        if db_file.owner_id == user.id:
            return True
        
        # Only admin can delete others' files
        if user.role == "admin":
            return True
        
        return False
    
    @staticmethod
    def log_access(
        db: Session,
        user_id: int,
        file_id: Optional[int],
        action_type: str,
        access_status: str,
        ip_address: Optional[str] = None,
        device_info: Optional[str] = None,
        is_anomalous: bool = False
    ):
        """
        Log file access for ML analysis and auditing
        
        Args:
            db: Database session
            user_id: User ID
            file_id: File ID (can be None for failed attempts)
            action_type: upload, download, delete
            access_status: granted, denied
            ip_address: Client IP address
            device_info: User-Agent string
            is_anomalous: Whether this access was flagged as anomalous
        """
        try:
            # Evaluate anomaly dynamically
            is_anom, score = anomaly_detector.detect_anomaly(
                db=db,
                user_id=user_id,
                file_id=file_id,
                action_type=action_type,
                access_status=access_status
            )
            
            access_log = models.AccessLog(
                user_id=user_id,
                file_id=file_id,
                action_type=action_type,
                access_status=access_status,
                ip_address=ip_address,
                device_info=device_info,
                is_anomalous=is_anom,
                anomaly_score=score
            )
            db.add(access_log)
            db.commit()
            db.refresh(access_log)
            return access_log
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Audit log failure for user {user_id}, file {file_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Audit log failure"
            )


# Global service instance
file_service = FileService()
