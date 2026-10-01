"""Quick test: verify PostgreSQL connection from DATABASE_URL in .env"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from sqlalchemy import create_engine, text

print(f"DATABASE_URL = {settings.DATABASE_URL}")
print(f"Connecting...")

engine = create_engine(settings.DATABASE_URL)
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.scalar()
        print(f"[OK] Connected successfully!")
        print(f"   PostgreSQL version: {version}")

        # Check if any tables exist
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = [row[0] for row in result]
        if tables:
            print(f"   Existing tables: {', '.join(tables)}")
        else:
            print(f"   No tables yet (empty database -- ready for migrations)")
except Exception as e:
    print(f"[FAIL] Connection failed: {e}")
    sys.exit(1)
