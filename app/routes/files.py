"""
File Routes
Handles file upload, download, and deletion with encryption and access logging
"""
import os
import uuid
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, cast
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from app import models, schemas, auth
from app.database import get_db
from app.encryption import encryption_manager
from app.config import settings
from app.blockchain_service import get_blockchain_service

# Initialize router
router = APIRouter(prefix="/files", tags=["files"])

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# Set up logging
logger = logging.getLogger(__name__)

# Upload constraints
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {
    ".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".csv", ".json", ".xml",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".mp4", ".mp3", ".wav", ".avi", ".mov",
    ".py", ".js", ".ts", ".html", ".css", ".md",
}


@router.post("/upload", response_model=schemas.FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and encrypt a file
    
    - Generates SHA-256 hash for blockchain anchoring
    - Encrypts file content
    - Stores encrypted file
    - Logs access with IP and device info
    
    Requires valid JWT token
    """
    try:
        user_id = cast(int, current_user.id)  # Cache user_id early
        
        # Validate file extension
        filename = file.filename or "unnamed"
        _, ext = os.path.splitext(filename)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{ext}' is not allowed. Permitted types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size
        if len(file_content) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds the {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB limit"
            )
        
        # Generate SHA-256 hash (blockchain-ready)
        file_hash = encryption_manager.generate_file_hash(file_content)
        
        # Encrypt file content
        encrypted_content = encryption_manager.encrypt_file(file_content)
        
        # Generate unique filename for encrypted file
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        encrypted_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        # Save encrypted file
        with open(encrypted_path, "wb") as f:
            f.write(encrypted_content)
        
        # Create file record in database
        db_file = models.File(
            filename=file.filename,
            encrypted_path=encrypted_path,
            file_hash=file_hash,
            owner_id=user_id
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        file_id = cast(int, db_file.id)
        
        # Log access
        ip_address = request.client.host if request.client else None
        device_info = request.headers.get("user-agent", None)
        from app.file_service import file_service
        access_log = file_service.log_access(
            db=db,
            user_id=user_id,
            file_id=file_id,
            action_type="upload",
            access_status="granted",
            ip_address=ip_address,
            device_info=device_info,
            is_anomalous=False
        )
        
        # Upload to blockchain (non-blocking attempt)
        blockchain_status = "NOT_ANCHORED"
        tx_hash_result = None
        
        # Get blockchain service and check if ready
        bc_service = get_blockchain_service()
        
        # Initialize blockchain service if not already done
        if not bc_service.is_ready:
            bc_service.initialize()
        
        if bc_service.is_ready:
            try:
                filename = file.filename or "unnamed_file"
                blockchain_result = bc_service.upload_file_to_blockchain(file_hash, filename)
                # Re-fetch to update with blockchain data
                db_file_update = db.query(models.File).filter(models.File.id == file_id).first()
                if db_file_update:
                    db_file_update.blockchain_tx_hash = blockchain_result.tx_hash
                    # Get the blockchain index from total files count (index = totalFiles - 1)
                    try:
                        total_files = bc_service.get_total_files()
                        blockchain_index = total_files - 1
                        if blockchain_index >= 0:
                            db_file_update.blockchain_index = blockchain_index
                            logger.info(f"Assigned blockchain_index={blockchain_index} to file_id={file_id}")
                        else:
                            db_file_update.blockchain_index = None
                            logger.error(f"Computed negative blockchain_index for file_id={file_id} (total_files={total_files})")
                    except Exception as index_error:
                        logger.error(f"Failed to get blockchain_index for file_id={file_id}: {str(index_error)}")
                        db_file_update.blockchain_index = None
                    db.commit()
                    blockchain_status = "ANCHORED"
                    tx_hash_result = blockchain_result.tx_hash
                    logger.info(f"File {file_id} successfully anchored to blockchain: {blockchain_result.tx_hash}")
            except Exception as e:
                # Log error but don't fail the request
                logger.error(f"Blockchain upload failed for file {file_id}: {str(e)}")
                # File remains in database with blockchain fields as None
                # In a real app, we might want to queue this for retry
        else:
            logger.info(f"Blockchain not available, skipping anchoring for file {file_id}")
        
        # Re-query to ensure fresh attached object (avoid DetachedInstanceError)
        db_file_fresh = db.query(models.File).filter(models.File.id == file_id).first()
        if not db_file_fresh:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File record not found after upload"
            )
        
        return {
            "id": db_file_fresh.id,
            "filename": db_file_fresh.filename,
            "file_hash": db_file_fresh.file_hash,
            "owner_id": db_file_fresh.owner_id,
            "upload_time": db_file_fresh.upload_time,
            "is_deleted": db_file_fresh.is_deleted,
            "blockchain_tx_hash": db_file_fresh.blockchain_tx_hash,
            "blockchain_index": db_file_fresh.blockchain_index,
            "is_anomalous": access_log.is_anomalous if access_log else None
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        # Log failed upload attempt
        ip_address = request.client.host if request.client else None
        device_info = request.headers.get("user-agent", None)
        from app.file_service import file_service
        # Try to log failure access if possible
        try:
            uid = user_id if 'user_id' in locals() else cast(int, current_user.id)
            file_service.log_access(
                db=db,
                user_id=uid,
                file_id=None,
                action_type="upload",
                access_status="denied",
                ip_address=ip_address,
                device_info=device_info,
                is_anomalous=False
            )
        except Exception as log_error:
            logger.error(f"Failed to log denied upload attempt: {str(log_error)}")
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )


@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    verify_hash: bool = True
):
    """
    Download and decrypt a file with hash verification
    """
    from app.file_service import file_service
    
    # Get file from database
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    
    # If file not found OR is_deleted=True -> raise 404 for ALL users including admin
    if not db_file or (db_file.is_deleted if db_file.is_deleted is not None else False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # If not owner AND not admin -> call create_access_log with status="denied", then raise 403
    has_access = file_service.verify_file_access(db_file, current_user)
    if not has_access:
        ip_address = request.client.host if request.client else None
        device_info = request.headers.get("user-agent", None)
        file_service.log_access(
            db=db,
            user_id=cast(int, current_user.id),
            file_id=file_id,
            action_type="download",
            access_status="denied",
            ip_address=ip_address,
            device_info=device_info
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You don't have permission to access this file."
        )
    
    try:
        # Process download with hash verification
        decrypted_content, filename = file_service.process_download(db_file, verify_hash=verify_hash)
        
        # On success -> call create_access_log with status="success"
        ip_address = request.client.host if request.client else None
        device_info = request.headers.get("user-agent", None)
        file_service.log_access(
            db=db,
            user_id=cast(int, current_user.id),
            file_id=file_id,
            action_type="download",
            access_status="granted",
            ip_address=ip_address,
            device_info=device_info
        )
        
        # Return file as streaming response
        return StreamingResponse(
            BytesIO(decrypted_content),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File download failed"
        )


@router.delete("/{file_id}", status_code=status.HTTP_200_OK)
async def delete_file(
    file_id: int,
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Soft delete a file (maintains audit trail)
    """
    from app.file_service import file_service

    # Query the file FIRST
    db_file = db.query(models.File).filter(models.File.id == file_id).first()
    
    # If not found OR already is_deleted=True → raise 404 immediately
    if not db_file or db_file.is_deleted is not None and db_file.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Check ownership: if file.owner_id != current_user.id AND role != "admin" → raise 403
    if db_file.owner_id != cast(int, current_user.id) and current_user.role != "admin":
        ip_address = request.client.host if request.client else None
        device_info = request.headers.get("user-agent", None)
        file_service.log_access(
            db=db,
            user_id=cast(int, current_user.id),
            file_id=file_id,
            action_type="delete",
            access_status="denied",
            ip_address=ip_address,
            device_info=device_info,
            is_anomalous=False
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You don't have permission to delete this file."
        )
    
    # Only THEN set is_deleted = True and commit
    db_file.is_deleted = True
    db.commit()
    
    # Call create_access_log() with action_type="delete", access_status="granted"
    ip_address = request.client.host if request.client else None
    device_info = request.headers.get("user-agent", None)
    file_service.log_access(
        db=db,
        user_id=cast(int, current_user.id),
        file_id=file_id,
        action_type="delete",
        access_status="granted",
        ip_address=ip_address,
        device_info=device_info,
        is_anomalous=False
    )
    
    return {"detail": "File deleted successfully", "file_id": file_id}


@router.get("/", response_model=List[schemas.FileResponse])
async def list_user_files(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    include_deleted: bool = False
):
    """
    List all files owned by the current user
    
    - **include_deleted**: Include soft-deleted files (default: False)
    
    Requires valid JWT token
    """
    query = db.query(models.File).filter(models.File.owner_id == cast(int, current_user.id))
    
    if not include_deleted:
        query = query.filter(models.File.is_deleted.is_(False))
    
    files = query.all()
    return files


@router.get("/{file_id}/verify")
async def verify_file_integrity(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Verify file integrity against storage and blockchain record.
    Always returns HTTP 200 — check integrity_ok in the response body.
    Tampering triggers an anomalous access_log row (status=denied).
    """
    from app.file_service import file_service

    ip_address = request.client.host if request.client else None
    device_info = request.headers.get("user-agent", None)

    # 1. Query file
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.is_deleted.is_(False)
    ).first()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # 2. Physical existence — backend storage problem, not tampering -> 500
    encrypted_path = str(file.encrypted_path)
    if not os.path.exists(encrypted_path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File missing from storage"
        )

    try:
        with open(encrypted_path, "rb") as f:
            encrypted_content = f.read()

        # 3. Attempt decryption — InvalidToken / any failure = tampered ciphertext
        try:
            decrypted_content = encryption_manager.decrypt_file(encrypted_content)
        except Exception:
            logger.warning(
                f"[TAMPER] File {file_id} failed decryption (user={current_user.id})"
            )
            file_service.log_access(
                db=db,
                user_id=cast(int, current_user.id),
                file_id=file_id,
                action_type="verify",
                access_status="denied",
                ip_address=ip_address,
                device_info=device_info,
                is_anomalous=True,
            )
            return {
                "file_id": file_id,
                "filename": file.filename,
                "stored_hash": file.file_hash,
                "current_hash": None,
                "integrity_ok": False,
                "tamper_reason": "Decryption failed — the encrypted file has been modified or corrupted.",
                "blockchain_verified": None,
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }

        # 4. Hash comparison
        current_hash = hashlib.sha256(decrypted_content).hexdigest()
        hash_matches = (current_hash == file.file_hash)

        if not hash_matches:
            logger.warning(
                f"[TAMPER] File {file_id} hash mismatch "
                f"(stored={file.file_hash[:12]}, current={current_hash[:12]}, user={current_user.id})"
            )
            file_service.log_access(
                db=db,
                user_id=cast(int, current_user.id),
                file_id=file_id,
                action_type="verify",
                access_status="denied",
                ip_address=ip_address,
                device_info=device_info,
                is_anomalous=True,
            )

        # 5. Blockchain check (independent; unanchored != tampered)
        blockchain_match = None
        bc_service = get_blockchain_service()
        if bc_service.is_enabled:
            try:
                if file.blockchain_index is not None:
                    blockchain_data = bc_service.get_file_from_blockchain(cast(int, file.blockchain_index))
                    blockchain_hash = blockchain_data["file_hash"]
                    blockchain_match = (blockchain_hash == file.file_hash)
            except Exception as e:
                logger.error(f"Blockchain verification failed for file {file_id}: {str(e)}")
                blockchain_match = None

        return {
            "file_id": file_id,
            "filename": file.filename,
            "stored_hash": file.file_hash,
            "current_hash": current_hash,
            "integrity_ok": hash_matches,
            "blockchain_verified": blockchain_match,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        # Unexpected I/O or other errors — safe generic message, no detail leak
        logger.error(f"Unexpected integrity-check error for file {file_id}: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Integrity check failed due to an internal error.",
        )

