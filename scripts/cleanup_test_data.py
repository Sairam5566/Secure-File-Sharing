"""
Cleanup script: delete all e2e/fix test users, their files (DB rows + disk files),
and their access_logs from the dev database.

Targets usernames used across all test scripts:
  e2e_regular_user, e2e_admin_forced, e2e_admin_real,
  fix1_user, fix2_admin, fix2_user, pg_verify_user,
  blockchain_test_user
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app import models

TEST_USERNAMES = [
    "e2e_regular_user", "e2e_admin_forced", "e2e_admin_real",
    "fix1_user", "fix2_admin", "fix2_user", "pg_verify_user",
    "blockchain_test_user",
]

def cleanup():
    print("=" * 60)
    print("Cleanup: removing e2e/fix test data from dev database")
    print("=" * 60)

    db = SessionLocal()
    try:
        users = db.query(models.User).filter(
            models.User.username.in_(TEST_USERNAMES)
        ).all()

        if not users:
            print("No test users found — nothing to clean up.")
            return

        for user in users:
            print(f"\nProcessing user: '{user.username}' (id={user.id})")

            # Collect files to delete from disk
            files = db.query(models.File).filter(
                models.File.owner_id == user.id
            ).all()
            for f in files:
                path = f.encrypted_path
                if os.path.exists(path):
                    os.remove(path)
                    print(f"  [DELETED DISK] {path}")
                else:
                    print(f"  [ALREADY GONE] {path}")

            # Delete access_logs referencing this user's files
            file_ids = [f.id for f in files]
            if file_ids:
                db.query(models.AccessLog).filter(
                    models.AccessLog.file_id.in_(file_ids)
                ).delete(synchronize_session=False)

            # Delete access_logs by user_id
            db.query(models.AccessLog).filter(
                models.AccessLog.user_id == user.id
            ).delete(synchronize_session=False)

            # Delete files
            db.query(models.File).filter(
                models.File.owner_id == user.id
            ).delete(synchronize_session=False)

            # Delete user
            db.delete(user)
            print(f"  [DELETED DB]   user '{user.username}' + files + access_logs")

        # Also clean up orphan access_logs with NULL user_id (from failed login tests)
        orphans = db.query(models.AccessLog).filter(
            models.AccessLog.user_id == None,
            models.AccessLog.action_type == "login",
        ).count()
        if orphans:
            db.query(models.AccessLog).filter(
                models.AccessLog.user_id == None,
                models.AccessLog.action_type == "login",
            ).delete(synchronize_session=False)
            print(f"\n[DELETED DB] {orphans} orphan login-denied log row(s) (NULL user_id)")

        db.commit()
        print("\n" + "=" * 60)
        print("Cleanup complete. Remaining DB state:")

        remaining_users = db.query(models.User).count()
        remaining_files = db.query(models.File).count()
        remaining_logs  = db.query(models.AccessLog).count()
        print(f"  Users: {remaining_users}")
        print(f"  Files: {remaining_files}")
        print(f"  AccessLogs: {remaining_logs}")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Cleanup failed: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
