"""
Dependencies Module
Centralized dependency injection functions for FastAPI routes
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, auth

# OAuth2 scheme for JWT token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user_dependency(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Reusable dependency to get current authenticated user
    
    This is a wrapper around auth.get_current_user for consistency
    """
    return auth.get_current_user(token=token, db=db)


def require_admin(current_user: models.User = Depends(get_current_user_dependency)) -> models.User:
    """
    Dependency that requires admin role
    
    Raises:
        HTTPException: 403 if user is not admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_admin_or_auditor(current_user: models.User = Depends(get_current_user_dependency)) -> models.User:
    """
    Dependency that requires admin or auditor role
    
    Raises:
        HTTPException: 403 if user is not admin or auditor
    """
    if current_user.role not in ["admin", "auditor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or auditor access required"
        )
    return current_user
