"""
Access Log Routes
Provides access to file access logs for ML analysis and auditing
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app import models, schemas, auth
from app.database import get_db
from app.ml.anomaly_detector import anomaly_detector

# Initialize router
router = APIRouter(prefix="/access-logs", tags=["access-logs"])


@router.get("/", response_model=List[schemas.AccessLogResponse])
async def get_access_logs(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    file_id: Optional[int] = Query(None, description="Filter by file ID"),
    action_type: Optional[str] = Query(None, description="Filter by action type (upload/download/delete)"),
    is_anomalous: Optional[bool] = Query(None, description="Filter to anomalous (true) or normal (false) events"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip")
):
    """
    Retrieve access logs for ML analysis and auditing
    
    **Access Control:**
    - Admin/Auditor: Can view all access logs
    - Regular users: Can only view their own logs
    
    **Filters:**
    - user_id: Filter by specific user
    - file_id: Filter by specific file
    - action_type: Filter by action (upload/download/delete)
    - start_date: Filter logs after this date
    - end_date: Filter logs before this date
    - limit: Maximum records to return (1-1000)
    - offset: Pagination offset
    
    **Returns:**
    List of access logs with IP address, device info, and action type for ML analysis
    """
    # Build base query
    query = db.query(models.AccessLog)
    
    # Role-based access control
    if current_user.role not in ["admin", "auditor"]:
        # Regular users can only see their own logs
        query = query.filter(models.AccessLog.user_id == current_user.id)
    else:
        # Admin/auditor can filter by user_id if provided
        if user_id is not None:
            query = query.filter(models.AccessLog.user_id == user_id)
    
    # Apply filters
    if file_id is not None:
        query = query.filter(models.AccessLog.file_id == file_id)
    
    if action_type is not None:
        if action_type not in ["upload", "download", "delete", "verify", "login"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid action_type. Must be one of: upload, download, delete, verify, login"
            )
        query = query.filter(models.AccessLog.action_type == action_type)
    
    if is_anomalous is not None:
        query = query.filter(models.AccessLog.is_anomalous.is_(is_anomalous))
    
    if start_date is not None:
        query = query.filter(models.AccessLog.access_time >= start_date)
    
    if end_date is not None:
        query = query.filter(models.AccessLog.access_time <= end_date)
    
    # Order by most recent first
    query = query.order_by(models.AccessLog.access_time.desc())
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    # Execute query
    logs = query.all()
    
    return logs


@router.get("/stats")
async def get_access_stats(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get access statistics for the current user or all users (admin/auditor only)
    
    Returns summary statistics useful for ML analysis and monitoring
    """
    # Determine which user's stats to show
    if current_user.role in ["admin", "auditor"]:
        # Admin/auditor can see all stats
        user_filter: Optional[int] = None
    else:
        # Regular users see only their stats
        user_filter = current_user.id
    
    # Build base query
    base_query = db.query(models.AccessLog)
    if user_filter is not None:
        base_query = base_query.filter(models.AccessLog.user_id == user_filter)
    
    # Calculate statistics
    total_accesses = base_query.count()
    
    upload_count = base_query.filter(models.AccessLog.action_type == "upload").count()
    download_count = base_query.filter(models.AccessLog.action_type == "download").count()
    delete_count = base_query.filter(models.AccessLog.action_type == "delete").count()
    
    granted_count = base_query.filter(models.AccessLog.access_status == "granted").count()
    denied_count = base_query.filter(models.AccessLog.access_status == "denied").count()
    
    # Get recent activity (last 10 logs)
    recent_logs = base_query.order_by(models.AccessLog.access_time.desc()).limit(10).all()
    
    # Check for anomaly using in-memory detector event count
    user_id_to_check = user_filter if user_filter else 0  # 0 means check all users for admin
    is_anomalous = False
    anomaly_count = 0
    
    if user_filter is not None:
        # For specific user, check their event count
        event_count = len(anomaly_detector._user_events.get(user_filter, []))
        is_anomalous = event_count > anomaly_detector.threshold
        anomaly_count = event_count if is_anomalous else 0
    else:
        # For admin, check all users
        for uid, events in anomaly_detector._user_events.items():
            if len(events) > anomaly_detector.threshold:
                is_anomalous = True
                anomaly_count += 1
    
    return {
        "total_accesses": total_accesses,
        "by_action": {
            "upload": upload_count,
            "download": download_count,
            "delete": delete_count
        },
        "by_status": {
            "granted": granted_count,
            "denied": denied_count
        },
        "is_anomalous": is_anomalous,
        "anomaly_count": anomaly_count,
        "recent_activity": [
            {
                "id": log.id,
                "action_type": log.action_type,
                "access_status": log.access_status,
                "access_time": log.access_time,
                "ip_address": log.ip_address
            }
            for log in recent_logs
        ]
    }
