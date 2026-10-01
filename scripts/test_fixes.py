"""
Test Fix 1: /files/{id}/verify returns HTTP 200 with integrity_ok=False on tampering.
Test Fix 2: Admin integrity scan separates local_integrity_ok from blockchain_anchored.
Test Fix 3: Failed logins are logged in access_logs.
"""
import sys, os, json, requests, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app import models
from app.auth import hash_password

BASE = "http://127.0.0.1:8000"
SEP = "=" * 64


def seed_user(username, email, password, role="user"):
    db = SessionLocal()
    try:
        u = db.query(models.User).filter(models.User.username == username).first()
        if u:
            db.delete(u)
            db.commit()
        user = models.User(
            username=username, email=email,
            hashed_password=hash_password(password), role=role
        )
        db.add(user)
        db.commit()
    finally:
        db.close()


def login(username, password):
    r = requests.post(f"{BASE}/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def upload_file(token, content=b"Fix-test content. Confidential.", name="fix_test.txt"):
    r = requests.post(
        f"{BASE}/files/upload",
        headers=auth_headers(token),
        files={"file": (name, content, "text/plain")},
    )
    assert r.status_code == 201, f"Upload failed: {r.text}"
    return r.json()


# ─────────────────────────────────────────────────
# FIX 1: verify returns 200 + integrity_ok=False on tamper
# ─────────────────────────────────────────────────
def test_fix1_verify_tampering():
    print(SEP)
    print("FIX 1: /files/{id}/verify — tamper detection without 500")
    print(SEP)

    seed_user("fix1_user", "fix1@example.com", "Fix1Pass123!")
    token = login("fix1_user", "Fix1Pass123!")

    # Upload
    upload = upload_file(token)
    file_id = upload["id"]
    print(f"Uploaded file id={file_id}")

    # Get disk path from DB
    db = SessionLocal()
    try:
        f = db.query(models.File).filter(models.File.id == file_id).first()
        enc_path = f.encrypted_path
    finally:
        db.close()

    print(f"Encrypted path: {enc_path}")

    # Verify BEFORE tamper — must be OK
    r = requests.get(f"{BASE}/files/{file_id}/verify", headers=auth_headers(token))
    print(f"\n[Before tamper] Status: {r.status_code}")
    print(f"Response: {json.dumps(r.json(), indent=2)}")
    assert r.status_code == 200
    assert r.json()["integrity_ok"] is True, "Expected integrity_ok=True before tamper"
    print("[PASS] Before tamper: integrity_ok=True")

    # Tamper: flip a byte
    with open(enc_path, "r+b") as fh:
        fh.seek(10)
        b = fh.read(1)
        fh.seek(10)
        fh.write(bytes([b[0] ^ 0xFF]))
    print("\nFile tampered on disk.")

    # Verify AFTER tamper
    r = requests.get(f"{BASE}/files/{file_id}/verify", headers=auth_headers(token))
    print(f"\n[After tamper] Status: {r.status_code}")
    body = r.json()
    print(f"Response: {json.dumps(body, indent=2)}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert body["integrity_ok"] is False, "Expected integrity_ok=False after tamper"
    assert "tamper_reason" in body, "Expected tamper_reason in response"
    assert body["current_hash"] is None, "Expected current_hash=None when decryption fails"
    print("[PASS] After tamper: HTTP 200, integrity_ok=False, tamper_reason present, no 500")

    # Verify access_log was written with status=denied, is_anomalous=True
    db = SessionLocal()
    try:
        logs = db.query(models.AccessLog).filter(
            models.AccessLog.file_id == file_id,
            models.AccessLog.action_type == "verify",
            models.AccessLog.access_status == "denied",
            models.AccessLog.is_anomalous == True,
        ).all()
        print(f"\nAnomalous verify logs written: {len(logs)}")
        for l in logs:
            print(f"  ID={l.id}, user_id={l.user_id}, status={l.access_status}, anomalous={l.is_anomalous}")
        assert len(logs) >= 1, "Expected at least 1 anomalous access_log row"
    finally:
        db.close()
    print("[PASS] Anomalous access_log row written for tamper event")

    # Restore
    with open(enc_path, "r+b") as fh:
        fh.seek(10)
        fh.write(b)
    print("File restored.")
    print()


# ─────────────────────────────────────────────────
# FIX 2: Admin scan — separate local_integrity_ok from blockchain_anchored
# NOTE: We test this after Fix 2 is applied to admin.py
# For now we just call the current scan and show the raw output so we can compare
# ─────────────────────────────────────────────────
def test_fix2_show_current_scan():
    print(SEP)
    print("FIX 2: Admin scan — current output (before fix)")
    print(SEP)

    seed_user("fix2_admin", "fix2admin@example.com", "Fix2Admin123!", role="admin")
    admin_token = login("fix2_admin", "Fix2Admin123!")

    r = requests.get(f"{BASE}/admin/scan-integrity", headers=auth_headers(admin_token))
    print(f"Scan status: {r.status_code}")
    print(f"Scan output:\n{json.dumps(r.json(), indent=2)}")
    print()


# ─────────────────────────────────────────────────
# FIX 3: Failed logins logged in access_logs
# ─────────────────────────────────────────────────
def test_fix3_failed_login_logging():
    print(SEP)
    print("FIX 3: Failed login logging in access_logs")
    print(SEP)

    # Count existing login-denied rows before
    db = SessionLocal()
    try:
        before = db.query(models.AccessLog).filter(
            models.AccessLog.action_type == "login",
            models.AccessLog.access_status == "denied",
        ).count()
    finally:
        db.close()
    print(f"Login-denied rows BEFORE: {before}")

    # Attempt a bad login
    r = requests.post(f"{BASE}/login", data={"username": "nonexistent_user", "password": "wrongpass"})
    print(f"Failed login status: {r.status_code}, body: {r.json()}")
    assert r.status_code == 401, f"Expected 401 for bad credentials, got {r.status_code}"

    # Count after
    db = SessionLocal()
    try:
        after = db.query(models.AccessLog).filter(
            models.AccessLog.action_type == "login",
            models.AccessLog.access_status == "denied",
        ).all()
        print(f"Login-denied rows AFTER:  {len(after)}")
        for l in after:
            print(f"  ID={l.id}, user_id={l.user_id}, ip={l.ip_address}, anomalous={l.is_anomalous}, time={l.access_time}")
    finally:
        db.close()

    new_rows = len(after) - before
    if new_rows >= 1:
        print(f"[PASS] {new_rows} new login-denied row(s) written")
    else:
        print("[FAIL] No new login-denied row — Fix 3 not yet applied")
    print()


if __name__ == "__main__":
    test_fix1_verify_tampering()
    test_fix2_show_current_scan()
    test_fix3_failed_login_logging()
    print("=" * 64)
    print("All fix verification tests complete.")
    print("=" * 64)
