"""
Database Configuration Module
PostgreSQL connection via SQLAlchemy with connection pooling
"""
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# Engine Configuration — PostgreSQL only
# ============================================================================

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # Verify connections are alive before checkout
    pool_size=5,           # Persistent connections in the pool
    max_overflow=10,       # Additional connections allowed beyond pool_size
    echo=settings.DEBUG,   # Log SQL queries in debug mode
)

logger.info(
    "Database engine created: host=%s, pool_size=5, max_overflow=10",
    settings.DATABASE_URL.split("@")[-1].split("/")[0] if "@" in settings.DATABASE_URL else "local",
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for ORM models
Base = declarative_base()


def get_db():
    """
    FastAPI dependency — yields a DB session and ensures cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create all tables defined in models (safe to call repeatedly).
    """
    from app import models  # noqa: F401 — import registers models with Base
    Base.metadata.create_all(bind=engine)
