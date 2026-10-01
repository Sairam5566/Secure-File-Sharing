import requests
import time

BASE_URL = "http://127.0.0.1:8000/api"

print("Testing Stricter /login limit (5/minute)...")
# Send 6 login requests
for i in range(1, 7):
    resp = requests.post(f"{BASE_URL}/login", data={"username": "fake", "password": "fake"})
    print(f"Request {i}: Status Code = {resp.status_code}")
    if resp.status_code == 429:
        print(f"Got 429 Rate Limit Exceeded on request {i}!")
        break
    time.sleep(0.1)

print("\nTesting Global limit on /register (60/minute)...")
# We will just hit an endpoint 65 times. Wait, /register creates users so it might fail with 400.
# A 400 response STILL counts towards the rate limit!
for i in range(1, 65):
    resp = requests.post(f"{BASE_URL}/register", json={"username": f"u{i}", "email": f"e{i}@test.com", "password": "password"})
    if i % 10 == 0 or i > 60:
        print(f"Request {i}: Status Code = {resp.status_code}")
    if resp.status_code == 429:
        print(f"Got 429 Rate Limit Exceeded on request {i}!")
        break
    time.sleep(0.01)
