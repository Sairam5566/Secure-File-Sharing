
import sys
import os
import requests
import json

# Add parent directory to path to allow importing app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings

def test_full_upload_flow():
    print("Testing Full Upload Flow...")
    
    # 1. Login to get token
    login_url = "http://127.0.0.1:8000/login"
    # Assuming a default user exists or we need to create one. 
    # For this test, let's try to register a new user first to be safe.
    
    register_url = "http://127.0.0.1:8000/register"
    user_data = {
        "username": "blockchain_test_user",
        "email": "blockchain_test@example.com",
        "password": "strongpassword123",
        "role": "user"
    }
    
    print(f"Registering user: {user_data['username']}")
    response = requests.post(register_url, json=user_data)
    if response.status_code == 201:
        print("User registered successfully.")
    elif response.status_code == 400 and "already registered" in response.text:
        print("User already exists.")
    else:
        print(f"Registration failed: {response.text}")
        # Proceeding to login anyway in case it failed because user exists
        
    print("Logging in...")
    login_data = {
        "username": "blockchain_test_user",
        "password": "strongpassword123"
    }
    response = requests.post(login_url, json=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        sys.exit(1)
        
    token = response.json()["access_token"]
    print("Login successful. Token received.")
    
    # 2. Upload file
    upload_url = "http://127.0.0.1:8000/files/upload"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("blockchain_test.txt", "This is a test file for blockchain integration.")}
    
    print("Uploading file...")
    response = requests.post(upload_url, headers=headers, files=files)
    
    if response.status_code != 201:
        print(f"Upload failed: {response.text}")
        sys.exit(1)
        
    file_data = response.json()
    print("Upload successful!")
    print(json.dumps(file_data, indent=2))
    
    # 3. Verify blockchain_tx_hash
    tx_hash = file_data.get("blockchain_tx_hash")
    if tx_hash:
        print(f"PASS: Blockchain transaction hash found: {tx_hash}")
    else:
        print("FAIL: Blockchain transaction hash missing.")
        sys.exit(1)

if __name__ == "__main__":
    test_full_upload_flow()
