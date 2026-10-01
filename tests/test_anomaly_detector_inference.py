import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import joblib

from app.ml.anomaly_detector import AnomalyDetector
from app.config import settings
from app import models

class TestAnomalyDetectorInference(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        # Ensure we don't accidentally load a real model in these tests
        self.original_model_path = settings.MODEL_PATH
        settings.MODEL_PATH = "dummy_non_existent_path.joblib"

    def tearDown(self):
        settings.MODEL_PATH = self.original_model_path

    def test_fallback_when_model_file_missing(self):
        detector = AnomalyDetector()
        self.assertIsNone(detector.model)
        
        # Test it falls back to rule-based
        is_anom, score = detector.detect_anomaly(self.mock_db, user_id=1, file_id=1, action_type="download")
        self.assertFalse(is_anom)
        self.assertIsNone(score)

    @patch('app.ml.anomaly_detector.joblib.load')
    @patch('app.ml.anomaly_detector.os.path.exists')
    def test_fallback_on_corrupted_bundle(self, mock_exists, mock_load):
        mock_exists.return_value = True
        # Missing 'features' key
        mock_load.return_value = {"model": "fake", "threshold": 0.05}
        
        detector = AnomalyDetector()
        self.assertIsNone(detector.model)

    @patch('app.ml.anomaly_detector.joblib.load')
    @patch('app.ml.anomaly_detector.os.path.exists')
    def test_score_sign_and_threshold(self, mock_exists, mock_load):
        mock_exists.return_value = True
        
        mock_model = MagicMock()
        # Mock decision_function to return a high negative score (normal)
        mock_model.decision_function.return_value = [0.1]
        
        mock_load.return_value = {
            "model": mock_model,
            "threshold": 0.05,
            "features": ["f1"]
        }
        
        detector = AnomalyDetector()
        self.assertIsNotNone(detector.model)
        # Threshold should be -0.05
        self.assertAlmostEqual(detector.ml_threshold, -0.05)
        
        # Mock DB query
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Mock compute_user_features
        with patch('app.ml.anomaly_detector.compute_user_features') as mock_cuf:
            mock_cuf.return_value = {"f1": 0.0}
            
            # Since decision_function returns 0.1, score = -0.1
            # -0.1 is NOT > -0.05, so is_anomalous = False
            is_anom, score = detector.detect_anomaly(self.mock_db, user_id=1, file_id=1, action_type="download")
            
            self.assertFalse(is_anom)
            self.assertAlmostEqual(score, -0.1)

            # Now mock an anomaly (negative decision_function)
            mock_model.decision_function.return_value = [-0.2]
            # score = 0.2
            # 0.2 > -0.05, so is_anomalous = True
            is_anom, score = detector.detect_anomaly(self.mock_db, user_id=1, file_id=1, action_type="download")
            
            self.assertTrue(is_anom)
            self.assertAlmostEqual(score, 0.2)

    @patch('app.ml.anomaly_detector.joblib.load')
    @patch('app.ml.anomaly_detector.os.path.exists')
    def test_scoring_exception_fallback(self, mock_exists, mock_load):
        mock_exists.return_value = True
        
        mock_model = MagicMock()
        # Raise exception during scoring
        mock_model.decision_function.side_effect = Exception("Test scoring failure")
        
        mock_load.return_value = {
            "model": mock_model,
            "threshold": 0.05,
            "features": ["f1"]
        }
        
        detector = AnomalyDetector()
        
        # Mock DB query
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        
        with patch('app.ml.anomaly_detector.compute_user_features') as mock_cuf:
            mock_cuf.return_value = {"f1": 0.0}
            
            # Should catch exception and fallback to rule-based smoothly
            # returning (False, None) for a single request
            is_anom, score = detector.detect_anomaly(self.mock_db, user_id=1, file_id=1, action_type="download")
            self.assertFalse(is_anom)
            self.assertIsNone(score)

    def test_model_path_from_config(self):
        # Just asserts the default config points to joblib
        self.assertTrue(settings.MODEL_PATH.endswith(".joblib"))

    def test_real_model_scoring(self):
        """
        Integration test that loads the ACTUAL saved bundle and scores
        a normal window vs an attack window (burst downloads, off-hours, failed logins).
        """
        # Ensure we use the real bundle for this test
        settings.MODEL_PATH = self.original_model_path
        detector = AnomalyDetector()
        
        self.assertIsNotNone(detector.model, f"Real model not found at {settings.MODEL_PATH}")
            
        now = datetime(2023, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
        
        # 1. Normal window
        normal_logs = [
            # user 999
            models.AccessLog(user_id=999, file_id=10, action_type="download", access_status="granted", access_time=now - timedelta(minutes=14)),
            models.AccessLog(user_id=999, file_id=11, action_type="upload", access_status="granted", access_time=now - timedelta(minutes=7)),
            models.AccessLog(user_id=999, file_id=12, action_type="download", access_status="granted", access_time=now - timedelta(minutes=2))
        ]
        
        self.mock_db.query.return_value.filter.return_value.all.return_value = normal_logs
        
        # Action that completes the normal window
        # Mock datetime.now inside detect_anomaly to use 'now'
        with patch('app.ml.anomaly_detector.datetime') as mock_dt:
            mock_dt.now.return_value = now
            is_anom_normal, score_normal = detector.detect_anomaly(self.mock_db, user_id=999, file_id=13, action_type="download")
        
        self.assertFalse(is_anom_normal, f"Normal window was falsely flagged as anomalous! Score: {score_normal}, Thresh: {detector.ml_threshold}")
        print(f"\nReal Model Normal Score: {score_normal:.4f} (Threshold: {detector.ml_threshold:.4f})")

        # 2. Attack window (burst, failed logins, off-hours)
        attack_now = datetime(2023, 10, 24, 2, 0, 0, tzinfo=timezone.utc) # 2 AM
        attack_logs = []
        # Burst downloads
        for i in range(15):
            attack_logs.append(
                models.AccessLog(user_id=888, file_id=50+i, action_type="download", access_status="granted", access_time=attack_now - timedelta(seconds=100-i))
            )
        # Repeated failed logins
        for i in range(5):
            attack_logs.append(
                models.AccessLog(user_id=888, file_id=None, action_type="login", access_status="denied", access_time=attack_now - timedelta(seconds=50-i))
            )
            
        self.mock_db.query.return_value.filter.return_value.all.return_value = attack_logs
        
        with patch('app.ml.anomaly_detector.datetime') as mock_dt:
            mock_dt.now.return_value = attack_now
            is_anom_attack, score_attack = detector.detect_anomaly(self.mock_db, user_id=888, file_id=100, action_type="download")
            
        self.assertTrue(is_anom_attack, f"Attack window was NOT flagged! Score: {score_attack}, Thresh: {detector.ml_threshold}")
        print(f"Real Model Attack Score: {score_attack:.4f} (Threshold: {detector.ml_threshold:.4f})")

if __name__ == '__main__':
    unittest.main()
