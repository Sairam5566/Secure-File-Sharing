from app.database import SessionLocal
from app.models import User
from app.auth import hash_password

db = SessionLocal()
admin = db.query(User).filter(User.username == "e2e_admin").first()
if not admin:
    admin = User(
        username="e2e_admin",
        email="e2e_admin@example.com",
        hashed_password=hash_password("AdminPassword123!"),
        role="admin"
    )
    db.add(admin)
    db.commit()
    print("Created e2e_admin user")
else:
    print("e2e_admin already exists")
db.close()
