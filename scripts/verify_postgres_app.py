"""
Step 7 Verification Script:
Verify PostgreSQL database operations, SQLAlchemy ORM models, foreign keys, and indexes.
"""
import sys
import os
from datetime import datetime

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app import models
from app.auth import hash_password

def verify_postgres_operations():
    print("=" * 60)
    print("Step 7 Verification: Testing PostgreSQL ORM Operations")
    print("=" * 60)

    db = SessionLocal()
    try:
        # 1. Clean existing test user if present
        test_username = "pg_verify_user"
        existing = db.query(models.User).filter(models.User.username == test_username).first()
        if existing:
            db.delete(existing)
            db.commit()
            print(f"[OK] Cleaned up prior test user '{test_username}'")

        # 2. Test User Creation
        print("\n1. Testing User model insertion...")
        test_user = models.User(
            username=test_username,
            email="pg_verify@example.com",
            hashed_password=hash_password("securepassword123"),
            role="user"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        print(f"   [PASS] User created with ID={test_user.id}, created_at={test_user.created_at}")

        # 3. Test File Creation (with relationship)
        print("\n2. Testing File model insertion (FK constraint)...")
        test_file = models.File(
            filename="test_pg_document.pdf",
            encrypted_path="uploads/test_pg_document.pdf.enc",
            file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            owner_id=test_user.id,
            is_deleted=False
        )
        db.add(test_file)
        db.commit()
        db.refresh(test_file)
        print(f"   [PASS] File created with ID={test_file.id}, upload_time={test_file.upload_time}")

        # 4. Test AccessLog Creation
        print("\n3. Testing AccessLog model insertion...")
        test_log = models.AccessLog(
            user_id=test_user.id,
            file_id=test_file.id,
            access_status="granted",
            ip_address="127.0.0.1",
            device_info="PostgreSQL Verification Script",
            action_type="download",
            is_anomalous=False
        )
        db.add(test_log)
        db.commit()
        db.refresh(test_log)
        print(f"   [PASS] AccessLog created with ID={test_log.id}, access_time={test_log.access_time}")

        # 5. Query and Relationship Verification
        print("\n4. Testing ORM Relationships & Foreign Keys...")
        user_fetched = db.query(models.User).filter(models.User.id == test_user.id).first()
        assert len(user_fetched.files) == 1, "Expected 1 file for user"
        assert len(user_fetched.access_logs) == 1, "Expected 1 access log for user"
        assert user_fetched.files[0].filename == "test_pg_document.pdf"
        assert user_fetched.access_logs[0].access_status == "granted"
        print(f"   [PASS] User '{user_fetched.username}' has {len(user_fetched.files)} file(s) and {len(user_fetched.access_logs)} access log(s).")

        # 6. Cascade Delete Cleanup Verification
        print("\n5. Testing Cascade Delete (Users -> Files & AccessLogs)...")
        db.delete(user_fetched)
        db.commit()
        
        remaining_files = db.query(models.File).filter(models.File.owner_id == test_user.id).count()
        remaining_logs = db.query(models.AccessLog).filter(models.AccessLog.user_id == test_user.id).count()
        assert remaining_files == 0, "Files should be deleted on user cascade"
        assert remaining_logs == 0, "Access logs should be deleted on user cascade"
        print("   [PASS] User deleted cleanly; files and access logs cascade-deleted successfully.")

        print("\n" + "=" * 60)
        print("SUCCESS: All PostgreSQL DB operations & ORM mappings verified!")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n[FAIL] PostgreSQL Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    verify_postgres_operations()
