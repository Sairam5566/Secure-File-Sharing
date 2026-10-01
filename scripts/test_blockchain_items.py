# -*- coding: utf-8 -*-
"""
Items 5, 6, 7 verification (ASCII-safe, sets PYTHONIOENCODING=utf-8 at top).

5 - Upload file, get blockchain tx hash, verify on-chain hash matches, /verify
    shows blockchain_verified: true.
6 - Tamper file_hash in Postgres, /verify and admin scan both flag mismatch.
7 - Failed login with known username stores that user's user_id in access_logs.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
import json
import requests
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app import models
from app.auth import hash_password
from app.blockchain_service import get_blockchain_service

BASE = "=" * 64


def login_api(username, password):
    r = requests.post("http://127.0.0.1:8000/login",
                      data={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def seed_user(username, email, password, role="user"):
    db = SessionLocal()
    try:
        u = db.query(models.User).filter(models.User.username == username).first()
        if u:
            for f in db.query(models.File).filter(models.File.owner_id == u.id).all():
                if os.path.exists(f.encrypted_path):
                    os.remove(f.encrypted_path)
            db.query(models.AccessLog).filter(
                models.AccessLog.user_id == u.id
            ).delete(synchronize_session=False)
            db.query(models.File).filter(
                models.File.owner_id == u.id
            ).delete(synchronize_session=False)
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


# ── ITEM 5 ─────────────────────────────────────────────────────────────────────
def test_item5_blockchain_upload_verify():
    print(BASE)
    print("ITEM 5: Upload -> blockchain anchoring -> /verify blockchain_verified=true")
    print(BASE)

    seed_user("bc_test_user", "bc_test@example.com", "BcTest123!")
    token = login_api("bc_test_user", "BcTest123!")

    print("Uploading file ...")
    original = b"Blockchain anchoring test content -- unique " + str(time.time()).encode()
    r = requests.post(
        "http://127.0.0.1:8000/files/upload",
        headers=auth_headers(token),
        files={"file": ("bc_anchor.txt", original, "text/plain")},
    )
    print(f"Upload status: {r.status_code}")
    up = r.json()
    print(f"Upload response:\n{json.dumps(up, indent=2)}")
    assert r.status_code == 201, f"Upload failed: {r.text}"

    file_id     = up["id"]
    tx_hash     = up.get("blockchain_tx_hash")
    bc_index    = up.get("blockchain_index")
    file_hash_db = up["file_hash"]

    print(f"\nFile ID        : {file_id}")
    print(f"DB file_hash   : {file_hash_db}")
    print(f"Blockchain tx  : {tx_hash}")
    print(f"Blockchain idx : {bc_index}")

    assert tx_hash,              "Expected blockchain_tx_hash to be set"
    assert bc_index is not None, "Expected blockchain_index to be set"

    # Read on-chain record
    print("\nQuerying on-chain record ...")
    bc = get_blockchain_service()
    if not bc.is_ready:
        bc.initialize()
    assert bc.is_ready, f"Blockchain service not ready: {bc.initialization_error}"

    chain_data = bc.get_file_from_blockchain(bc_index)
    print(f"On-chain record:\n{json.dumps({k: str(v) for k, v in chain_data.items()}, indent=2)}")

    assert chain_data["file_hash"] == file_hash_db, (
        f"On-chain hash mismatch!\n  DB   : {file_hash_db}\n"
        f"  Chain: {chain_data['file_hash']}"
    )
    print("[PASS] On-chain file_hash matches DB file_hash exactly")

    # /verify endpoint
    r_v = requests.get(
        f"http://127.0.0.1:8000/files/{file_id}/verify",
        headers=auth_headers(token),
    )
    print(f"\n/verify response:\n{json.dumps(r_v.json(), indent=2)}")
    assert r_v.status_code == 200
    v = r_v.json()
    assert v["integrity_ok"] is True,       "[FAIL] integrity_ok should be True"
    assert v["blockchain_verified"] is True, "[FAIL] blockchain_verified should be True"
    print("[PASS] /verify: integrity_ok=True, blockchain_verified=True")
    print()
    return file_id, file_hash_db, bc_index, token


# ── ITEM 6 ─────────────────────────────────────────────────────────────────────
def test_item6_db_tamper_blockchain_mismatch(file_id, original_hash, bc_index, token):
    print(BASE)
    print("ITEM 6: Tamper file_hash in Postgres -> /verify and admin scan flag mismatch")
    print(BASE)

    fake_hash = "a" * 64
    db = SessionLocal()
    try:
        f = db.query(models.File).filter(models.File.id == file_id).first()
        assert f, "File not found in DB"
        f.file_hash = fake_hash
        db.commit()
        print(f"DB file_hash overwritten to: {fake_hash[:12]}...")
    finally:
        db.close()

    # /verify: disk hash (decrypted) != fake DB hash -> integrity_ok=False
    #          chain hash != fake DB hash          -> blockchain_verified=False
    r_v = requests.get(
        f"http://127.0.0.1:8000/files/{file_id}/verify",
        headers=auth_headers(token),
    )
    print(f"\n/verify after DB tamper:\n{json.dumps(r_v.json(), indent=2)}")
    v = r_v.json()
    assert r_v.status_code == 200
    assert v["integrity_ok"] is False, \
        "[FAIL] integrity_ok should be False (disk hash != fake DB hash)"
    assert v["blockchain_verified"] is False, \
        "[FAIL] blockchain_verified should be False"
    print("[PASS] /verify: integrity_ok=False, blockchain_verified=False after DB tamper")

    # Admin scan
    seed_user("bc_admin", "bc_admin@example.com", "BcAdmin123!", role="admin")
    admin_token = login_api("bc_admin", "BcAdmin123!")
    r_scan = requests.get(
        "http://127.0.0.1:8000/admin/scan-integrity",
        headers=auth_headers(admin_token),
    )
    print(f"\nAdmin scan after DB tamper:\n{json.dumps(r_scan.json(), indent=2)}")
    scan = r_scan.json()
    assert r_scan.status_code == 200

    tampered      = scan.get("tampered_files", [])
    bc_mismatch   = scan.get("blockchain_mismatch", [])
    ids_tampered  = [e["file_id"] for e in tampered]
    ids_bcmismatch = [e["file_id"] for e in bc_mismatch]

    assert file_id in ids_tampered or file_id in ids_bcmismatch, (
        f"[FAIL] File {file_id} not flagged!\n"
        f"  tampered_files     : {ids_tampered}\n"
        f"  blockchain_mismatch: {ids_bcmismatch}"
    )
    print(
        f"[PASS] Admin scan flagged file {file_id} "
        f"(tampered={ids_tampered}, bc_mismatch={ids_bcmismatch})"
    )

    # Restore original hash
    db = SessionLocal()
    try:
        f = db.query(models.File).filter(models.File.id == file_id).first()
        f.file_hash = original_hash
        db.commit()
        print(f"\nDB file_hash restored to: {original_hash[:12]}...")
    finally:
        db.close()
    print()


# ── ITEM 7 ─────────────────────────────────────────────────────────────────────
def test_item7_failed_login_known_user():
    print(BASE)
    print("ITEM 7: Failed login with known username stores user_id (not NULL)")
    print(BASE)

    seed_user("known_logintest", "known_logintest@example.com", "KnownPass123!")

    db = SessionLocal()
    try:
        known_user = db.query(models.User).filter(
            models.User.username == "known_logintest"
        ).first()
        known_id = known_user.id
        print(f"Known user 'known_logintest' has id={known_id}")
    finally:
        db.close()

    # 1. Wrong password for a KNOWN user
    r1 = requests.post("http://127.0.0.1:8000/login",
                       data={"username": "known_logintest", "password": "WRONGPASSWORD"})
    assert r1.status_code == 401, f"Expected 401, got {r1.status_code}"
    print(f"\nFailed login (known user, wrong password): {r1.status_code} {r1.json()}")

    # 2. Completely unknown username
    r2 = requests.post("http://127.0.0.1:8000/login",
                       data={"username": "nobody_here_at_all", "password": "anything"})
    assert r2.status_code == 401
    print(f"Failed login (unknown user): {r2.status_code} {r2.json()}")

    db = SessionLocal()
    try:
        recent = (
            db.query(models.AccessLog)
            .filter(
                models.AccessLog.action_type == "login",
                models.AccessLog.access_status == "denied",
            )
            .order_by(models.AccessLog.id.desc())
            .limit(10)
            .all()
        )
        print(f"\nRecent login-denied access_log rows:")
        print(f"{'ID':<5} | {'user_id':<10} | {'ip':<15} | time")
        print("-" * 60)
        for l in recent:
            print(f"{l.id:<5} | {str(l.user_id):<10} | {str(l.ip_address):<15} | {l.access_time}")
    finally:
        db.close()

    # Assertions
    db = SessionLocal()
    try:
        known_fail = (
            db.query(models.AccessLog)
            .filter(
                models.AccessLog.user_id == known_id,
                models.AccessLog.action_type == "login",
                models.AccessLog.access_status == "denied",
            )
            .first()
        )
        null_fail = (
            db.query(models.AccessLog)
            .filter(
                models.AccessLog.user_id == None,
                models.AccessLog.action_type == "login",
                models.AccessLog.access_status == "denied",
            )
            .order_by(models.AccessLog.id.desc())
            .first()
        )
    finally:
        db.close()

    assert known_fail is not None, (
        f"[FAIL] No access_log row with user_id={known_id} for known-user failed login"
    )
    print(f"\n[PASS] Known-user failed login -> user_id={known_fail.user_id} (not NULL)")

    assert null_fail is not None, "[FAIL] No NULL user_id row for unknown-user failed login"
    print(f"[PASS] Unknown-user failed login -> user_id={null_fail.user_id} (NULL)")
    print()


if __name__ == "__main__":
    file_id, file_hash_db, bc_index, token = test_item5_blockchain_upload_verify()
    test_item6_db_tamper_blockchain_mismatch(file_id, file_hash_db, bc_index, token)
    test_item7_failed_login_known_user()
    print(BASE)
    print("ALL ITEMS 5, 6, 7 PASSED")
    print(BASE)
