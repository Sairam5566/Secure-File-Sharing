"""
User Routes
Handles user registration and authentication
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app import models, schemas, auth
from app.database import get_db
from app.ml.anomaly_detector import anomaly_detector

# Initialize router
router = APIRouter(prefix="", tags=["users"])

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

logger = logging.getLogger(__name__)


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    user_data: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    """
    Register a new user
    
    - **username**: Unique username (3-50 characters)
    - **email**: Valid email address
    - **password**: Password (minimum 8 characters)
    
    Role is always set to "user". Use the CLI script (scripts/create_admin.py) to create admin accounts.
    """
    # Check if username already exists
    existing_user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Role is always "user" — admin/auditor accounts must be created via CLI
    hashed_password = auth.hash_password(user_data.password)
    new_user = models.User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role="user"
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "role": new_user.role,
        "created_at": new_user.created_at
    }


@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token
    """
    # Build identifier = f"{request.client.host}:{form_data.username}"
    client_host = request.client.host if request.client else "unknown"
    identifier = f"{client_host}:{form_data.username}"
    
    # Call check_rate_limit(identifier) BEFORE authenticate_user()
    auth.check_rate_limit(identifier)
    
    # Authenticate user
    user = auth.authenticate_user(db, form_data.username, form_data.password)

    if not user:
        # Record failed brute-force attempt
        auth.record_failed_attempt(identifier)

        # Resolve user_id if the username exists (wrong password) — NULL if unknown user
        ip_address = request.client.host if request.client else None
        device_info = request.headers.get("user-agent", None)
        known = db.query(models.User).filter(
            models.User.username == form_data.username
        ).first()
        user_id_for_log = known.id if known else None

        # Write denied-login access_log for anomaly detection
        try:
            is_anom, score = anomaly_detector.detect_anomaly(
                db=db,
                user_id=user_id_for_log,
                file_id=None,
                action_type="login",
                access_status="denied"
            )
            log_entry = models.AccessLog(
                user_id=user_id_for_log,
                file_id=None,
                action_type="login",
                access_status="denied",
                ip_address=ip_address,
                device_info=device_info,
                is_anomalous=is_anom,
                anomaly_score=score
            )
            db.add(log_entry)
            db.commit()
        except Exception as log_err:
            db.rollback()
            logger.error(f"Failed to log denied login attempt: {log_err}")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # If authentication succeeds -> clear failed attempts
    auth.clear_failed_attempts(identifier)
    
    # Create access token
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Get current authenticated user information
    
    Requires valid JWT token
    """
    return current_user
