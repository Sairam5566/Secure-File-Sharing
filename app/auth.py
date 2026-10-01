"""
Authentication Module
Handles password hashing, JWT tokens, and RBAC
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from collections import defaultdict
from functools import wraps

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models, schemas


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for JWT token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# ============================================================================
# Password Hashing Functions
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    if len(password.encode('utf-8')) > 72:
        raise ValueError("Password must be 72 characters or fewer (bytes)")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# JWT Token Functions
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Dictionary containing token payload (username, role, etc.)
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[schemas.TokenData]:
    """
    Decode and validate a JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData object or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        if username is None:
            return None
        
        return schemas.TokenData(username=username, role=role)
    except JWTError:
        return None


# ============================================================================
# Authentication Dependencies
# ============================================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Dependency to get the current authenticated user from JWT token
    
    Args:
        token: JWT token from request header
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = decode_access_token(token)
    if token_data is None or token_data.username is None:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    
    return user


def get_current_active_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    Dependency to get current active user (can be extended with is_active field)
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        User object
    """
    return current_user


# ============================================================================
# Role-Based Access Control (RBAC)
# ============================================================================

def require_role(allowed_roles: List[str]):
    """
    Decorator factory for role-based access control
    
    Args:
        allowed_roles: List of roles allowed to access the endpoint
        
    Returns:
        Decorator function
        
    Example:
        @require_role(["admin", "auditor"])
        def admin_only_endpoint(current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: models.User = Depends(get_current_user), **kwargs):
            if current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


def check_user_role(user: models.User, allowed_roles: List[str]) -> bool:
    """
    Check if user has one of the allowed roles
    
    Args:
        user: User object
        allowed_roles: List of allowed roles
        
    Returns:
        True if user has allowed role, False otherwise
    """
    return user.role in allowed_roles


# ============================================================================
# Rate limiting state
_failed_attempts: dict[str, list[datetime]] = defaultdict(list)
MAX_ATTEMPTS = 5
WINDOW = timedelta(minutes=15)

def check_rate_limit(identifier: str):
    """
    Check if the identifier (IP + username) has exceeded the rate limit for failed login attempts.
    """
    now = datetime.now(timezone.utc)
    # Prune attempts older than WINDOW
    _failed_attempts[identifier] = [ts for ts in _failed_attempts[identifier] if now - ts < WINDOW]
    
    if len(_failed_attempts[identifier]) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again in 15 minutes.",
            headers={"Retry-After": "900"}
        )

def record_failed_attempt(identifier: str):
    """Record a failed login attempt."""
    _failed_attempts[identifier].append(datetime.now(timezone.utc))

def clear_failed_attempts(identifier: str):
    """Clear failed attempts on successful login."""
    _failed_attempts.pop(identifier, None)

# Authentication Helper Functions
# ============================================================================

def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    """
    Authenticate a user with username and password
    
    Args:
        db: Database session
        username: Username
        password: Plain text password
        
    Returns:
        User object if authentication successful, None otherwise
    """
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None
    if not verify_password(password, str(user.hashed_password)):
        return None
    return user
