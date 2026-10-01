import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import io
import os
from datetime import datetime

from app.main import app
from app.database import get_db
from app import models, auth

class TestRouteInference(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        
        # In-memory DB
        self.engine = create_engine(
            'sqlite:///:memory:', 
            connect_args={'check_same_thread': False},
            poolclass=StaticPool
        )
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create all tables
        models.Base.metadata.create_all(bind=self.engine)
        
        # Override get_db
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
                
        app.dependency_overrides[get_db] = override_get_db
        
        # Override auth
        self.mock_user = models.User(username="testuser", email="test@test.com", hashed_password="pw", role="user")
        
        # We need to put the user in the DB so that queries for it work
        db = TestingSessionLocal()
        db.add(self.mock_user)
        db.commit()
        db.refresh(self.mock_user)
        db.close()
        
        app.dependency_overrides[auth.get_current_user] = lambda: self.mock_user
        self.client = TestClient(app)
        
        # Provide dummy configuration for directories to avoid creating files in actual dirs
        from app.config import settings
        self.original_upload_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = "./tests/temp_uploads"
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    def tearDown(self):
        from app.config import settings
        settings.UPLOAD_DIR = self.original_upload_dir
        app.dependency_overrides.clear()
        
    @patch('app.ml.anomaly_detector.compute_user_features')
    @patch('app.routes.files.get_blockchain_service')
    def test_upload_download_success_on_scoring_exception(self, mock_get_bc, mock_compute):
        # Force an exception during feature extraction, which will trigger detect_anomaly's Exception catch
        mock_compute.side_effect = Exception("Forced feature extraction exception")
        
        # Mock blockchain to not fail
        mock_bc = MagicMock()
        mock_bc.is_ready = True
        mock_bc.upload_file_to_blockchain.return_value = MagicMock(tx_hash="0xhash")
        mock_bc.get_total_files.return_value = 1
        mock_get_bc.return_value = mock_bc
        
        # Upload testing
        file_content = b"dummy content"
        response = self.client.post(
            "/files/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        )
        self.assertIn(response.status_code, [200, 201], f"Upload failed: {response.text}")
        file_id = response.json()["id"]

        # Download testing
        response = self.client.get(f"/files/download/{file_id}")
        self.assertEqual(response.status_code, 200, f"Download failed: {response.text}")

    @patch('app.routes.files.get_blockchain_service')
    def test_new_user_first_action_not_flagged(self, mock_get_bc):
        # We don't mock detect_anomaly; we let it run with real or fallback model.
        # It should return is_anom=False since it's the first action.
        
        mock_bc = MagicMock()
        mock_bc.is_ready = True
        mock_bc.upload_file_to_blockchain.return_value = MagicMock(tx_hash="0xhash")
        mock_bc.get_total_files.return_value = 1
        mock_get_bc.return_value = mock_bc
        
        file_content = b"dummy"
        response = self.client.post(
            "/files/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        )
        self.assertIn(response.status_code, [200, 201])
        
        data = response.json()
        # The route returns is_anomalous=False (or None if log wasn't attached, but we attach it)
        self.assertFalse(data.get("is_anomalous"), "First action was flagged as anomalous!")

if __name__ == '__main__':
    unittest.main()
