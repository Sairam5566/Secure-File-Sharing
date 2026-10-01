import unittest
import os
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

from app import models
from app.database import engine, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.ml.background_job import rescore_active_users
from app.ml.anomaly_detector import anomaly_detector
from app.config import settings

# Setup in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=None)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class TestBackgroundJob(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        # Clean tables
        db = TestingSessionLocal()
        db.query(models.AccessLog).delete()
        db.commit()
        db.close()
        
        self.original_model_path = settings.MODEL_PATH
        
        # Override the SessionLocal in background_job to use our test DB
        self.patcher = patch('app.ml.background_job.SessionLocal', return_value=TestingSessionLocal())
        self.mock_session_local = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        settings.MODEL_PATH = self.original_model_path

    def test_job_updates_flags(self):
        # We need the real model loaded to rescore
        settings.MODEL_PATH = self.original_model_path
        anomaly_detector._load_model()
        
        db = TestingSessionLocal()
        
        now = datetime.now(timezone.utc)
        
        # Add normal logs for user 1 (will not be flagged)
        log1 = models.AccessLog(user_id=1, file_id=1, action_type="download", access_status="granted", access_time=now - timedelta(minutes=5))
        db.add(log1)
        
        # Add attack logs for user 2 (will be flagged)
        # 20 downloads in the last 15 minutes
        for i in range(20):
            db.add(models.AccessLog(user_id=2, file_id=2+i, action_type="download", access_status="granted", access_time=now - timedelta(minutes=2)))
            
        db.commit()
        
        # Run background job
        rescore_active_users()
        
        # Check updates
        user1_logs = db.query(models.AccessLog).filter(models.AccessLog.user_id == 1).order_by(models.AccessLog.id.desc()).all()
        user2_logs = db.query(models.AccessLog).filter(models.AccessLog.user_id == 2).order_by(models.AccessLog.id.desc()).all()
        
        print("\n--- Background Job Update Results ---")
        print(f"User 1 (Normal) latest log: is_anomalous={user1_logs[0].is_anomalous}, score={user1_logs[0].anomaly_score:.4f}")
        self.assertFalse(user1_logs[0].is_anomalous)
        
        print(f"User 2 (Attack) latest log: is_anomalous={user2_logs[0].is_anomalous}, score={user2_logs[0].anomaly_score:.4f}")
        self.assertTrue(user2_logs[0].is_anomalous)
        
        db.close()

    @patch('app.ml.background_job.compute_user_features')
    def test_job_swallows_exception(self, mock_compute):
        db = TestingSessionLocal()
        now = datetime.now(timezone.utc)
        db.add(models.AccessLog(user_id=3, file_id=1, action_type="download", access_status="granted", access_time=now))
        db.commit()
        db.close()
        
        # Force an exception
        mock_compute.side_effect = Exception("Forced exception in background job")
        
        # Should not raise exception
        try:
            rescore_active_users()
        except Exception as e:
            self.fail(f"Background job raised exception instead of swallowing: {e}")
            
        print("Background job successfully swallowed exception.")

if __name__ == '__main__':
    unittest.main()
