import logging
from app.ml.background_job import rescore_active_users
from app.database import engine, SessionLocal
from sqlalchemy import text
from app.config import settings

logging.basicConfig(level=logging.DEBUG)

print(f"Connecting to database: {settings.DATABASE_URL}")

print("\n--- First Run ---")
rescore_active_users()

print("\n--- Second Run ---")
rescore_active_users()

print("\n--- Concurrent Simulation ---")
# Simulate another worker holding the lock
db = SessionLocal()
db.execute(text("SELECT pg_try_advisory_lock(8888)"))
print("Main thread acquired lock 8888.")

print("Attempting to run job while lock is held...")
rescore_active_users()

print("Releasing lock from main thread...")
db.execute(text("SELECT pg_advisory_unlock(8888)"))
db.commit()
db.close()

print("\n--- Third Run (after lock released) ---")
rescore_active_users()

print("\nFinished Postgres lock test.")
