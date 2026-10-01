import unittest
from fastapi.testclient import TestClient
from app.main import app

class TestRateLimits(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_login_strict_limit(self):
        print("\nTesting Stricter /login limit (5/minute)...")
        for i in range(1, 7):
            response = self.client.post("/login", data={"username": "fake", "password": "fake"})
            print(f"Request {i}: Status Code = {response.status_code}")
            if i <= 5:
                # Should not be 429 yet
                self.assertNotEqual(response.status_code, 429)
            if i == 6:
                self.assertEqual(response.status_code, 429, "Request 6 did not get 429!")
                print(f"Got 429 Rate Limit Exceeded on request {i}!")

    def test_global_register_limit(self):
        print("\nTesting Global limit on /register (60/minute)...")
        for i in range(1, 65):
            response = self.client.post("/register", json={"username": f"u{i}", "email": f"e{i}@test.com", "password": "password"})
            if i % 10 == 0 or i > 60:
                print(f"Request {i}: Status Code = {response.status_code}")
            if i <= 60:
                self.assertNotEqual(response.status_code, 429)
            if i == 61:
                self.assertEqual(response.status_code, 429, "Request 61 did not get 429!")
                print(f"Got 429 Rate Limit Exceeded on request {i}!")
                break

if __name__ == '__main__':
    unittest.main()
