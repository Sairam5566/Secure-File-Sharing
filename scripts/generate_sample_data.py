import os
import sqlite3
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

print("Registering test user...")
resp = requests.post(f"{BASE_URL}/users/register", json={
    "username": "screenshot_user",
    "email": "screenshot@test.com",
    "password": "password123"
})

print("Logging in...")
resp = requests.post(f"{BASE_URL}/users/login", data={
    "username": "screenshot_user",
    "password": "password123"
})
token = resp.json().get("access_token")
if not token:
    print("Login failed")
    exit(1)
headers = {"Authorization": f"Bearer {token}"}

print("Uploading files...")
files_to_upload = [
    ("Q3_Financial_Report.pdf", b"%PDF-1.4..."),
    ("Customer_Data_Backup.zip", b"PK\x03\x04..."),
    ("Project_Alpha_Specs.docx", b"PK\x03\x04...docx...")
]

file_ids = []
for name, content in files_to_upload:
    with open(name, "wb") as f:
        f.write(content)
    
    with open(name, "rb") as f:
        resp = requests.post(f"{BASE_URL}/files/upload", headers=headers, files={"file": f})
    
    if resp.status_code == 201:
        file_ids.append(resp.json()["id"])
        print(f"Uploaded {name}")
    else:
        print(f"Upload failed: {resp.text}")
    os.remove(name)

# Tamper with the second file on disk
print("Tampering with file 2 on disk...")
# Find the encrypted_path from sqlite
db_path = "d:/Sairam/SECURE FILE SHARING/file_share.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()
# Wait, user might not have id 2... we just uploaded files, their IDs are in file_ids
tampered_id = file_ids[1]
c.execute("SELECT encrypted_path FROM files WHERE id = ?", (tampered_id,))
row = c.fetchone()
if row:
    encrypted_path = row[0]
    with open(encrypted_path, "ab") as f:
        f.write(b"TAMPERED")
    print(f"Appended tampering data to {encrypted_path}")

conn.close()
print("Done. Ready for screenshots.")
