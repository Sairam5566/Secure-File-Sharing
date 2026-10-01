
import sys
import os
sys.path.append(os.getcwd())
from app.auth import hash_password
from app import models
from app.database import SessionLocal
import json
from datetime import datetime

def test_hashing():
    pwd = "testpassword"
    hashed = hash_password(pwd)
    print(f"Type of hashed password: {type(hashed)}")
    print(f"Value: {hashed}")
    
    if isinstance(hashed, bytes):
        print("Hashed password IS bytes!")
    else:
        print("Hashed password is NOT bytes")

def test_serialization():
    # Simulate the return value of register_user
    user = models.User(
        id=1,
        username="test",
        email="test@test.com",
        role="user",
        created_at=datetime.now(),
        hashed_password=hash_password("password")
    )
    
    # Try to serialize
    try:
        # Pydantic serialization
        from app.schemas import UserResponse
        resp = UserResponse.model_validate(user)
        print("Pydantic validation successful")
        print(resp.model_dump_json())
    except Exception as e:
        print(f"Pydantic validation failed: {e}")

from app.auth import create_access_token

def test_token():
    data = {"sub": "testuser", "role": "user"}
    token = create_access_token(data)
    print(f"Token type: {type(token)}")
    print(f"Token value: {token}")

if __name__ == "__main__":
    test_hashing()
    test_serialization()
    test_token()
