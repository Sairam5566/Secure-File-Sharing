"""Admin Routes - Handles admin-only operations like system integrity scanning"""
import os
import hashlib
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from app.encryption import encryption_manager

from datetime import datetime

from app import models, auth
from app.database import get_db
from app.blockchain_service import get_blockchain_service

# Initialize router
router = APIRouter(prefix="/admin", tags=["admin"])

# Set up logging
logger = logging.getLogger(__name__)


@router.get("/scan-integrity")
async def scan_system_integrity(
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Admin-only system integrity scanner.

    For every non-deleted file, reports two independent fields per file:
      - local_integrity_ok: decryption succeeded AND hash matches DB record
      - blockchain_anchored: file has a blockchain_index AND hash matches blockchain

    An unanchored but locally intact file is counted in valid_files and
    listed in not_anchored — it is NOT counted as tampered.

    Requires admin role.
    """
    if current_user.role != "admin":
        logger.warning(f"Non-admin user {current_user.username} attempted integrity scan")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    logger.info(f"Starting system integrity scan by admin: {current_user.username}")

    scan_results = {
        "total_files_scanned": 0,
        "valid_files": 0,          # locally intact (decryption + hash OK)
        "tampered_files": [],       # decryption failed OR hash mismatch
        "missing_files": [],        # not on disk
        "not_anchored": [],         # intact but no blockchain record
        "blockchain_mismatch": [],  # blockchain hash != DB hash
    }

    try:
        files = db.query(models.File).filter(models.File.is_deleted.is_(False)).all()
        scan_results["total_files_scanned"] = len(files)
        logger.info(f"Found {len(files)} files to scan")

        for file in files:
            file_info = {
                "file_id": file.id,
                "filename": file.filename,
                "local_integrity_ok": False,
                "blockchain_anchored": file.blockchain_index is not None,
            }

            # ── 1. Physical existence check ──────────────────────────────
            if not os.path.exists(file.encrypted_path):
                file_info["reason"] = f"File not found at path: {file.encrypted_path}"
                scan_results["missing_files"].append(file_info)
                logger.error(f"File {file.id} missing from disk at {file.encrypted_path}")
                continue

            # ── 2. Local integrity: decrypt + hash ───────────────────────
            try:
                with open(file.encrypted_path, "rb") as f:
                    encrypted_content = f.read()
                decrypted_content = encryption_manager.decrypt_file(encrypted_content)
                calculated_hash = hashlib.sha256(decrypted_content).hexdigest()
            except Exception as e:
                file_info["reason"] = "Decryption failed — ciphertext has been modified or corrupted."
                scan_results["tampered_files"].append(file_info)
                logger.error(f"File {file.id} decryption failed: {type(e).__name__}")
                continue

            if calculated_hash != file.file_hash:
                file_info["reason"] = (
                    f"Hash mismatch (stored={file.file_hash[:12]}…, "
                    f"current={calculated_hash[:12]}…)"
                )
                scan_results["tampered_files"].append(file_info)
                logger.warning(f"File {file.id}: TAMPERED — local hash mismatch")
                continue

            # Local integrity is confirmed
            file_info["local_integrity_ok"] = True
            scan_results["valid_files"] += 1
            logger.debug(f"File {file.id}: local integrity OK")

            # ── 3. Blockchain check (independent, only if anchored) ───────
            if file.blockchain_index is None:
                scan_results["not_anchored"].append({
                    "file_id": file.id,
                    "filename": file.filename,
                    "local_integrity_ok": True,
                    "reason": "File is locally intact but not registered on blockchain.",
                })
                logger.info(f"File {file.id}: locally intact, not anchored on blockchain")
                continue

            bc_service = get_blockchain_service()
            if not bc_service.is_ready:
                logger.warning(f"Blockchain not available — skipping blockchain check for file {file.id}")
                # Don't penalise the file — blockchain is simply unavailable
                continue

            try:
                blockchain_data = bc_service.get_file_from_blockchain(file.blockchain_index)
                blockchain_hash = blockchain_data["file_hash"]
                if blockchain_hash != file.file_hash:
                    scan_results["blockchain_mismatch"].append({
                        "file_id": file.id,
                        "filename": file.filename,
                        "local_integrity_ok": True,
                        "reason": (
                            f"DB hash ({file.file_hash[:12]}…) differs from "
                            f"blockchain hash ({blockchain_hash[:12]}…)."
                        ),
                    })
                    logger.warning(f"File {file.id}: blockchain hash mismatch")
                else:
                    logger.debug(f"File {file.id}: blockchain verified OK")
            except Exception as e:
                logger.error(f"Blockchain check for file {file.id} failed: {str(e)}")
                # Blockchain temporarily unavailable — don't flag as tampered

        logger.info(
            f"Scan done. total={scan_results['total_files_scanned']}, "
            f"valid={scan_results['valid_files']}, "
            f"tampered={len(scan_results['tampered_files'])}, "
            f"missing={len(scan_results['missing_files'])}, "
            f"not_anchored={len(scan_results['not_anchored'])}, "
            f"bc_mismatch={len(scan_results['blockchain_mismatch'])}"
        )
        return scan_results

    except Exception as e:
        logger.error(f"Critical error during integrity scan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Integrity scan failed"
        )


@router.get("/anomaly-report")
async def get_anomaly_report(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Admin-only anomaly detection report.
    Returns statistics about anomalous access patterns detected by ML.
    Requires admin role.
    """
    if current_user.role != "admin":
        logger.warning("Non-admin user %s attempted to access anomaly report", current_user.username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        total_anomalies = db.query(models.AccessLog).filter(
            models.AccessLog.is_anomalous.is_(True)
        ).count()

        anomalous_logs = db.query(models.AccessLog).filter(
            models.AccessLog.is_anomalous.is_(True)
        ).order_by(models.AccessLog.access_time.desc()).offset(skip).limit(limit).all()

        anomalies = []
        for log in anomalous_logs:
            access_time: datetime = log.access_time  # type: ignore
            detection_source = "model" if log.anomaly_score is not None else "rule/fallback"
            
            anomalies.append({
                "id": log.id,
                "user_id": log.user_id,
                "timestamp": access_time.isoformat(),
                "action_type": log.action_type,
                "access_status": log.access_status,
                "anomaly_score": log.anomaly_score,
                "detection": detection_source,
            })

        report = {
            "total_anomalies": total_anomalies,
            "skip": skip,
            "limit": limit,
            "anomalies": anomalies,
        }

        logger.info("Anomaly report by admin %s: returning %d anomalies", current_user.username, len(anomalies))
        return report

    except Exception as e:
        logger.error(f"Failed to generate anomaly report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Anomaly report generation failed"
        )
