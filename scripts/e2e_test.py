import requests
import time
import uuid

BASE_URL = "http://127.0.0.1:8001"

def main():
    print("=== Step 1: Registration and Login ===")
    user_name = f"e2e_user_{uuid.uuid4().hex[:8]}"
    password = "SuperSecretPassword123!"
    
    # Register normal user
    res = requests.post(f"{BASE_URL}/register", json={
        "username": user_name,
        "email": f"{user_name}@example.com",
        "password": password
    })
    print(f"Register {user_name}: {res.status_code}")
    
    # Login normal user
    res = requests.post(f"{BASE_URL}/login", data={
        "username": user_name,
        "password": password
    })
    user_token = res.json().get("access_token")
    user_headers = {"Authorization": f"Bearer {user_token}"}
    print(f"Login {user_name}: {res.status_code}")

    # Login admin user (created via create_admin.py)
    admin_name = "e2e_admin"
    admin_pass = "AdminPassword123!"
    res = requests.post(f"{BASE_URL}/login", data={
        "username": admin_name,
        "password": admin_pass
    })
    admin_token = res.json().get("access_token")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print(f"Login {admin_name}: {res.status_code}")

    print("\n=== Step 2: Normal Upload and Download ===")
    # Upload a file
    files = {"file": ("test.txt", b"Hello from e2e test", "text/plain")}
    res = requests.post(f"{BASE_URL}/files/upload", headers=user_headers, files=files)
    print(f"Upload: {res.status_code} - {res.text}")
    file_id = res.json().get("id")

    # Download 3 times normally
    for i in range(3):
        res = requests.get(f"{BASE_URL}/files/download/{file_id}", headers=user_headers)
        print(f"Normal Download {i+1}: {res.status_code}")
        time.sleep(1)
        
    print("\n=== Step 3: Burst Test ===")
    print("Downloading the same file 25 times rapidly...")
    for i in range(25):
        res = requests.get(f"{BASE_URL}/files/download/{file_id}", headers=user_headers)
        if res.status_code != 200:
            print(f"Burst Download {i+1} failed: {res.status_code} - {res.text}")
        time.sleep(0.1)
    
    print("\n=== Step 4: Failed Login Test ===")
    print("Attempting 5 failed logins, then 1 success...")
    for i in range(5):
        res = requests.post(f"{BASE_URL}/login", data={
            "username": user_name,
            "password": "WrongPassword!"
        })
        print(f"Failed Login {i+1}: {res.status_code}")
    
    res = requests.post(f"{BASE_URL}/login", data={
        "username": user_name,
        "password": password
    })
    print(f"Successful Login after failures: {res.status_code}")

    print("\n=== Step 5: Admin Anomaly Report ===")
    time.sleep(2) # Give background tasks or DB a moment if necessary (though scoring is inline)
    res = requests.get(f"{BASE_URL}/admin/anomaly-report", headers=admin_headers)
    print(f"Anomaly Report: {res.status_code}")
    report = res.json()
    print(f"Total Anomalies: {report.get('total_anomalies')}")
    for anom in report.get('anomalies', [])[:10]:
        print(f" - Log ID: {anom['id']}, User: {anom['user_id']}, Action: {anom['action_type']}, Score: {anom['anomaly_score']}, Detection: {anom['detection']}")

    print("\n=== Step 6: Blockchain Verification ===")
    res = requests.get(f"{BASE_URL}/files/{file_id}/verify", headers=user_headers)
    print(f"Verify File: {res.status_code} - {res.json()}")

if __name__ == "__main__":
    main()
