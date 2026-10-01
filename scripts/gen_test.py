import requests
import sqlite3
import os
import uuid

BASE_URL = 'http://127.0.0.1:8000'
user_id = uuid.uuid4().hex[:8]
username = f"user_{user_id}"

r1 = requests.post(f'{BASE_URL}/register', json={'username': username, 'email': f'{username}@test.com', 'password': 'password123'})
print("Register:", r1.status_code, r1.text)

resp = requests.post(f'{BASE_URL}/login', data={'username': username, 'password': 'password123'})
print("Login:", resp.status_code, resp.text)
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

for name in ['Q3_Financial_Report.pdf', 'Customer_Data_Backup.zip', 'Project_Alpha_Specs.docx']:
    with open(name, 'wb') as f:
        f.write(b'dummy data')
    with open(name, 'rb') as f:
        r = requests.post(f'{BASE_URL}/files/upload', headers=headers, files={'file': f})
        print("Upload:", r.json())
    os.remove(name)

db_path = 'file_share.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute(f"SELECT id, encrypted_path FROM files WHERE owner_id = (SELECT id FROM users WHERE username = '{username}') LIMIT 3")
rows = c.fetchall()
tampered_id = rows[1][0]
encrypted_path = rows[1][1]
with open(encrypted_path, 'ab') as f:
    f.write(b'TAMPERED')
conn.close()
print('Tampered file ID:', tampered_id)
print('Username to login with:', username)
