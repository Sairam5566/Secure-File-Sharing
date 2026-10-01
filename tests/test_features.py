import unittest
import zoneinfo
from datetime import datetime, timedelta, timezone
from app.ml.features import compute_user_features, LogRow, is_off_hours

class TestFeatures(unittest.TestCase):
    def test_is_off_hours(self):
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        # Tuesday, 12:00 PM IST is NOT off hours
        dt1 = datetime(2023, 10, 24, 12, 0, 0, tzinfo=tz)
        self.assertFalse(is_off_hours(dt1))
        
        # Tuesday, 7:00 AM IST IS off hours
        dt2 = datetime(2023, 10, 24, 7, 0, 0, tzinfo=tz)
        self.assertTrue(is_off_hours(dt2))
        
        # Sunday, 12:00 PM IST IS off hours
        dt3 = datetime(2023, 10, 22, 12, 0, 0, tzinfo=tz)
        self.assertTrue(is_off_hours(dt3))
        
        # Test default conversion from UTC (12:00 PM UTC = 5:30 PM IST on Tuesday)
        # 5:30 PM is not off hours
        dt_utc = datetime(2023, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(is_off_hours(dt_utc))

        # 3:00 PM UTC = 8:30 PM IST (off hours)
        dt_utc_off = datetime(2023, 10, 24, 15, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(is_off_hours(dt_utc_off))

    def test_compute_user_features_empty(self):
        current_time = datetime.now(timezone.utc)
        features = compute_user_features([], current_time=current_time)
        self.assertEqual(features["requests_per_minute"], 0.0)
        self.assertEqual(features["distinct_files"], 0.0)

    def test_compute_user_features_single_event(self):
        # A Tuesday, 12:00 PM UTC = 5:30 PM IST (Not off-hours)
        base_time = datetime(2023, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
        logs = [
            LogRow(user_id=1, access_time=base_time, access_status="granted", action_type="download", file_id=1)
        ]
        features = compute_user_features(logs, current_time=base_time, window_minutes=15)
        
        self.assertEqual(features["requests_per_minute"], 1 / 15.0)
        self.assertEqual(features["distinct_files"], 1.0)
        self.assertEqual(features["download_to_upload_ratio"], 1.0)
        self.assertEqual(features["failed_access_ratio"], 0.0)
        self.assertEqual(features["off_hours_activity"], 0.0)
        self.assertEqual(features["avg_time_between_requests"], 0.0) # single event, division by zero is avoided!

    def test_compute_user_features_none_user(self):
        base_time = datetime(2023, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
        logs = [
            LogRow(user_id=None, access_time=base_time, access_status="granted", action_type="download", file_id=1)
        ]
        features = compute_user_features(logs, current_time=base_time, window_minutes=15)
        # Should be treated as empty
        self.assertEqual(features["requests_per_minute"], 0.0)

    def test_compute_user_features_basic(self):
        base_time = datetime(2023, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
        
        logs = [
            LogRow(user_id=1, access_time=base_time - timedelta(minutes=10), access_status="granted", action_type="download", file_id=1),
            LogRow(user_id=1, access_time=base_time - timedelta(minutes=5), access_status="granted", action_type="upload", file_id=2),
            LogRow(user_id=1, access_time=base_time - timedelta(minutes=2), access_status="denied", action_type="download", file_id=3),
        ]
        
        features = compute_user_features(logs, current_time=base_time, window_minutes=15)
        
        self.assertAlmostEqual(features["requests_per_minute"], 3 / 15)
        self.assertEqual(features["distinct_files"], 3.0)
        self.assertAlmostEqual(features["download_to_upload_ratio"], 2.0 / 1.0)
        self.assertAlmostEqual(features["failed_access_ratio"], 1.0 / 3.0)
        self.assertEqual(features["off_hours_activity"], 0.0)
        self.assertEqual(features["avg_time_between_requests"], 240.0)

    def test_ml_pipeline_feature_units(self):
        # A test to prove the raw-log fixture yields the correct order and units of features
        FEATURE_NAMES = [
            "requests_per_minute",
            "distinct_files",
            "download_to_upload_ratio",
            "failed_access_ratio",
            "off_hours_activity",
            "avg_time_between_requests"
        ]
        
        base_time = datetime(2023, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
        logs = [
            LogRow(user_id=1, access_time=base_time - timedelta(minutes=10), access_status="granted", action_type="download", file_id=1),
            LogRow(user_id=1, access_time=base_time - timedelta(minutes=5), access_status="granted", action_type="upload", file_id=2),
            LogRow(user_id=1, access_time=base_time - timedelta(minutes=2), access_status="failed_login", action_type="login", file_id=None),
        ]
        
        features_dict = compute_user_features(logs, current_time=base_time, window_minutes=15)
        
        # Verify units and bounds
        # RPM is events / window
        self.assertAlmostEqual(features_dict["requests_per_minute"], 3 / 15.0)
        
        # Distinct files is a raw count
        self.assertEqual(features_dict["distinct_files"], 2.0)
        
        # DL/UL ratio is float > 0
        self.assertAlmostEqual(features_dict["download_to_upload_ratio"], 1.0 / 1.0)
        
        # Ratios must be 0-1
        self.assertTrue(0.0 <= features_dict["failed_access_ratio"] <= 1.0)
        self.assertAlmostEqual(features_dict["failed_access_ratio"], 1.0 / 3.0)
        
        self.assertTrue(0.0 <= features_dict["off_hours_activity"] <= 1.0)
        
        # Time between requests is in seconds
        # 10m -> 5m (300s) -> 2m (180s). Average = 240s
        self.assertEqual(features_dict["avg_time_between_requests"], 240.0)
        
        # Ensure we can build the exact vector the model expects
        feature_vector = [features_dict[f] for f in FEATURE_NAMES]
        self.assertEqual(len(feature_vector), 6)
        self.assertEqual(feature_vector[0], features_dict["requests_per_minute"])

if __name__ == '__main__':
    unittest.main()
