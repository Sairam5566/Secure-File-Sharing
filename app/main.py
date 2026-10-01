"""
Main Application Entry Point
FastAPI application with security hardening, CORS, rate limiting, and global error handling
"""
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db
from app.routes import users, files, access, admin
from app.ml.background_job import start_background_jobs, stop_background_jobs

logger = logging.getLogger(__name__)


# ============================================================================
# Application Lifespan Events
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    Handles startup and shutdown tasks
    """
    # Startup: Initialize database
    logger.info("Starting application...")
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")
    
    start_background_jobs()
    
    yield
    
    # Shutdown
    stop_background_jobs()
    logger.info("Shutting down application...")

# ============================================================================
# Initialize FastAPI Application
# ============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    **Secure Cloud File Sharing System** with patent-grade architecture
    
    ## Features
    - 🔐 **JWT Authentication** with role-based access control (RBAC)
    - 🔒 **AES-128 Encryption** for file storage
    - 🔗 **Blockchain-Ready** SHA-256 file hashing
    - 🤖 **ML-Ready** access pattern logging
    - 🗑️ **Soft Delete** for audit compliance
    - 🚦 **Rate Limiting** for security
    
    ## Roles
    - **user**: Standard user with file upload/download capabilities
    - **admin**: Full access including file deletion and user management
    - **auditor**: Read-only access to all files and logs
    
    ## Phase Roadmap
    - ✅ **Phase 1**: Backend Core Foundation (Current)
    - 🔜 **Phase 2**: Blockchain Smart Contract Integration
    - 🔜 **Phase 3**: ML Anomaly Detection + TPM 2.0 Hardware Security
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


from slowapi.middleware import SlowAPIMiddleware

# ============================================================================
# Rate Limiting Setup
# ============================================================================

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ============================================================================
# CORS Middleware (Restricted Origins)
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # Restricted to configured origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Global Exception Handlers (Consistent JSON Responses)
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors with consistent JSON format
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors()
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """
    Handle ValueError exceptions (e.g., bcrypt password length errors)
    """
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unexpected errors
    """
    exc_str = str(exc)
    
    # Specifically catch pydantic validator error
    if "password_too_long" in exc_str:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": [
                    {
                        "loc": ["body", "password"],
                        "msg": "password cannot be longer than 72 bytes",
                        "type": "value_error.any_str.max_length",
                        "ctx": {"limit_value": 72}
                    }
                ]
            }
        )
    
    # Specifically catch bcrypt password length error to return 422
    if "password cannot be longer than 72 bytes" in exc_str:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": [
                    {
                        "loc": ["body", "password"],
                        "msg": "password cannot be longer than 72 bytes",
                        "type": "value_error.any_str.max_length",
                        "ctx": {"limit_value": 72}
                    }
                ]
            }
        )
    
    logger.error(f"Global exception caught: {type(exc).__name__}: {exc_str}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error": exc_str if settings.DEBUG else "An unexpected error occurred"
        }
    )


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(users.router)
app.include_router(files.router)
app.include_router(access.router)
app.include_router(admin.router)


# ============================================================================
# Health Check Endpoint
# ============================================================================

@app.get("/health", tags=["health"])
async def health_check():
    """
    Enhanced health check endpoint
    
    Verifies:
    - Application status
    - Database connection
    - Encryption key availability
    
    Returns detailed health status
    """
    from app.database import engine
    from app.encryption import encryption_manager
    import os
    from typing import Any
    
    health_status: dict[str, Any] = {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "phase": "Phase 1: Backend Core Foundation",
        "checks": {}
    }
    
    # Check database connection
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {
            "status": "connected",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "disconnected",
            "message": f"Database connection failed: {str(e)}"
        }
    
    # Check encryption key availability
    try:
        key_path = settings.ENCRYPTION_KEY_PATH
        if os.path.exists(key_path):
            # Verify key can be used
            test_data = b"health_check_test"
            encrypted = encryption_manager.encrypt_file(test_data)
            decrypted = encryption_manager.decrypt_file(encrypted)
            if decrypted == test_data:
                health_status["checks"]["encryption"] = {
                    "status": "available",
                    "message": "Encryption key loaded and functional"
                }
            else:
                health_status["status"] = "unhealthy"
                health_status["checks"]["encryption"] = {
                    "status": "error",
                    "message": "Encryption/decryption test failed"
                }
        else:
            health_status["status"] = "unhealthy"
            health_status["checks"]["encryption"] = {
                "status": "missing",
                "message": f"Encryption key not found at {key_path}"
            }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["encryption"] = {
            "status": "error",
            "message": f"Encryption check failed: {str(e)}"
        }
    
    # Check blockchain health (optional - don't fail health check if disabled)
    try:
        from app.blockchain_service import get_blockchain_service
        bc = get_blockchain_service()
        if bc.enabled:
            try:
                connected = bc.w3.is_connected() if bc.w3 else False
                bc_status = {
                    "enabled": True,
                    "connected": connected,
                    "contract_loaded": bc.contract is not None
                }
            except Exception as e:
                bc_status = {"enabled": True, "connected": False, "error": str(e)}
        else:
            bc_status = {"enabled": False, "connected": None}
        
        health_status["checks"]["blockchain"] = bc_status
        # Don't mark unhealthy if blockchain is just disabled
        if bc.enabled and not bc.is_ready:
            health_status["status"] = "degraded"
            health_status["checks"]["blockchain"]["note"] = "Blockchain configured but not available"
    except Exception as e:
        health_status["checks"]["blockchain"] = {
            "status": "error",
            "message": f"Blockchain health check failed: {str(e)}"
        }
    
    from datetime import datetime, timezone
    health_status["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    return health_status


@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint with API information
    """
    return {
        "message": "Welcome to Secure Cloud File Sharing System",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }
