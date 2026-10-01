import sys
import os

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine, SessionLocal

def add_column():
    db = SessionLocal()
    try:
        # Check if column exists
        check_query = text("SELECT column_name FROM information_schema.columns WHERE table_name='files' AND column_name='blockchain_tx_hash'")
        result = db.execute(check_query).fetchone()
        
        if not result:
            print("Adding blockchain_tx_hash column...")
            alter_query = text("ALTER TABLE files ADD COLUMN blockchain_tx_hash VARCHAR(66)")
            db.execute(alter_query)
            db.commit()
            print("Column added successfully.")
        else:
            print("Column already exists.")
            
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_column()
