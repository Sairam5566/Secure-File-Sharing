"""
CLI Script: Create Admin or Auditor User
Run from the project root:  python -m scripts.create_admin

This is the ONLY safe way to create privileged accounts.
The /register API endpoint always assigns role="user".
"""
import sys
import os
import getpass

# Ensure project root is on sys.path so `app.*` imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app import models
from app.auth import hash_password


def create_privileged_user():
    print("=" * 50)
    print("  Create Admin / Auditor User")
    print("=" * 50)

    username = input("Username: ").strip()
    if not username or len(username) < 3:
        print("Error: Username must be at least 3 characters.")
        sys.exit(1)

    email = input("Email: ").strip()
    if not email or "@" not in email:
        print("Error: Invalid email address.")
        sys.exit(1)

    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("Error: Password must be at least 8 characters.")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    print("\nAvailable roles: admin, auditor")
    role = input("Role: ").strip().lower()
    if role not in ("admin", "auditor"):
        print("Error: Role must be 'admin' or 'auditor'.")
        sys.exit(1)

    # Initialize DB tables if needed
    init_db()

    db = SessionLocal()
    try:
        # Check for duplicates
        if db.query(models.User).filter(models.User.username == username).first():
            print(f"Error: Username '{username}' already exists.")
            sys.exit(1)

        if db.query(models.User).filter(models.User.email == email).first():
            print(f"Error: Email '{email}' already registered.")
            sys.exit(1)

        # Create the user
        hashed = hash_password(password)
        user = models.User(
            username=username,
            email=email,
            hashed_password=hashed,
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"\n✅ {role.capitalize()} user created successfully!")
        print(f"   ID:       {user.id}")
        print(f"   Username: {user.username}")
        print(f"   Email:    {user.email}")
        print(f"   Role:     {user.role}")
    finally:
        db.close()


if __name__ == "__main__":
    create_privileged_user()
