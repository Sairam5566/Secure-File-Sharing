import os
import sys
import numpy as np
import joblib
from datetime import datetime, timedelta, timezone
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import random
from unittest.mock import patch

# Determine the project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from app.ml.features import compute_user_features, LogRow
from app.ml.anomaly_detector import AnomalyDetector

FEATURE_NAMES = [
    "requests_per_minute",
    "distinct_files",
    "download_to_upload_ratio",
    "failed_access_ratio",
    "off_hours_activity",
    "avg_time_between_requests"
]

def generate_raw_user_logs(user_id, user_type, end_time, window_minutes=15):
    """
    Generate raw logs for a single user ending at end_time.
    user_type: 'normal_std', 'normal_bulk', 'normal_night', 'anomaly_slow', 'anomaly_off', 'anomaly_fail'
    Returns a list of LogRow objects.
    """
    logs = []
    start_time = end_time - timedelta(minutes=window_minutes)
    
    if user_type == 'normal_std':
        n_events = int(random.gammavariate(2.0, 0.5) * window_minutes)
        n_events = max(1, n_events)
        file_pool = [random.randint(1, 5) for _ in range(5)]
        dl_ul = 2.0
    elif user_type == 'normal_bulk':
        n_events = int(random.gammavariate(5.0, 2.0) * window_minutes)
        n_events = max(5, n_events)
        file_pool = [random.randint(1, 50) for _ in range(20)]
        dl_ul = 5.0
    elif user_type == 'normal_night':
        n_events = int(random.gammavariate(2.0, 1.0) * window_minutes)
        n_events = max(1, n_events)
        file_pool = [random.randint(1, 10) for _ in range(5)]
        dl_ul = 1.0
        # Force end_time to be off-hours (e.g., 2 AM)
        end_time = end_time.replace(hour=2)
        start_time = end_time - timedelta(minutes=window_minutes)
    elif user_type == 'anomaly_slow':
        # Burst: many downloads in short time
        n_events = int(random.gammavariate(10.0, 1.5) * window_minutes)
        file_pool = [random.randint(100, 150) for _ in range(30)]
        dl_ul = 20.0
    elif user_type == 'anomaly_off':
        n_events = int(random.gammavariate(5.0, 2.0) * window_minutes)
        file_pool = [random.randint(200, 250) for _ in range(30)]
        dl_ul = 5.0
        end_time = end_time.replace(hour=3)
        start_time = end_time - timedelta(minutes=window_minutes)
    elif user_type == 'anomaly_fail':
        n_events = int(random.gammavariate(3.0, 2.0) * window_minutes)
        n_events = max(5, n_events)
        file_pool = [random.randint(300, 305) for _ in range(2)]
        dl_ul = 1.0
    else:
        n_events = 5
        file_pool = [1, 2]
        dl_ul = 1.0

    # Generate random timestamps
    timestamps = []
    for _ in range(n_events):
        offset = random.uniform(0, window_minutes * 60)
        timestamps.append(start_time + timedelta(seconds=offset))
    timestamps.sort()
    
    # Optional: explicitly trigger same-file rule for 'anomaly_slow'
    if user_type == 'anomaly_slow' and len(timestamps) >= 3 and random.random() < 0.5:
        # clump 3 downloads in 5 seconds
        target_ts = timestamps[len(timestamps)//2]
        timestamps[0] = target_ts + timedelta(seconds=1)
        timestamps[1] = target_ts + timedelta(seconds=2)
        timestamps[2] = target_ts + timedelta(seconds=3)
        timestamps.sort()
        file_pool = [1000] # same file
        dl_ul = 100.0 # pure downloads
    
    for i, ts in enumerate(timestamps):
        # Determine action
        action = "download" if random.random() < (dl_ul / (dl_ul + 1)) else "upload"
        
        # Determine status
        status = "granted"
        if user_type == 'anomaly_fail':
            if random.random() < 0.8: # 80% fail rate
                status = "failed_login"
        else:
            if random.random() < 0.02: # 2% normal fail rate
                status = "denied"
                
        # File ID
        fid = random.choice(file_pool) if status != "failed_login" else None
        
        logs.append(LogRow(user_id=user_id, access_time=ts, access_status=status, action_type=action, file_id=fid))
        
    return logs

def generate_dataset(n_samples, user_types, current_time):
    X = []
    raw_windows = []
    
    for i, u_type in enumerate(user_types):
        # Generate raw logs
        logs = generate_raw_user_logs(user_id=i, user_type=u_type, end_time=current_time)
        
        # Pass through REAL pipeline
        features_dict = compute_user_features(logs, current_time)
        
        # Assemble feature vector
        vec = [features_dict[f] for f in FEATURE_NAMES]
        X.append(vec)
        raw_windows.append(logs)
        
    return np.array(X), raw_windows

def evaluate_rule_based(raw_windows):
    """
    Evaluate the raw test windows using the real AnomalyDetector.
    Since AnomalyDetector relies on datetime.now(timezone.utc), we mock it for each event.
    """
    y_pred = []
    for logs in raw_windows:
        # Fresh detector per user window
        detector = AnomalyDetector()
        is_anom = False
        
        for log in logs:
            with patch('app.ml.anomaly_detector.datetime') as mock_datetime:
                # AnomalyDetector uses aware UTC time
                mock_datetime.now.return_value = log.access_time.replace(tzinfo=timezone.utc)
                
                # Check anomaly (pass None for db since rule fallback doesn't use it)
                is_anom_rule, _ = detector.detect_anomaly(None, log.user_id, log.file_id, log.action_type)
                if is_anom_rule:
                    is_anom = True
                    break # window is anomalous if any event triggers it
        
        y_pred.append(-1 if is_anom else 1)
        
    return np.array(y_pred)

def main():
    print("Generating synthetic RAW log datasets...")
    random.seed(42)
    np.random.seed(42)
    
    current_time = datetime(2023, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
    
    # Train set (Normal only)
    train_types = ['normal_std']*4200 + ['normal_bulk']*900 + ['normal_night']*900
    random.shuffle(train_types)
    X_train, _ = generate_dataset(6000, train_types, current_time)
    
    # Validation set
    val_types = ['normal_std']*1050 + ['normal_bulk']*225 + ['normal_night']*225 + \
                ['anomaly_slow']*60 + ['anomaly_off']*45 + ['anomaly_fail']*45
    random.shuffle(val_types)
    X_val, _ = generate_dataset(1650, val_types, current_time)
    y_val = np.array([-1 if 'anomaly' in t else 1 for t in val_types])
    
    # Test set
    test_types = ['normal_std']*1400 + ['normal_bulk']*300 + ['normal_night']*300 + \
                 ['anomaly_slow']*80 + ['anomaly_off']*60 + ['anomaly_fail']*60
    random.shuffle(test_types)
    X_test, raw_test_windows = generate_dataset(2200, test_types, current_time)
    y_test = np.array([-1 if 'anomaly' in t else 1 for t in test_types])
    
    print(f"Training set (normal only): {X_train.shape}")
    print(f"Validation set: {X_val.shape} (Anomalies: {sum(y_val == -1)})")
    print(f"Test set: {X_test.shape} (Anomalies: {sum(y_test == -1)})")
    
    print("\nTraining IsolationForest model...")
    clf = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
    clf.fit(X_train)
    
    print("\nTuning threshold on validation set...")
    val_scores = clf.decision_function(X_val)
    normal_val_scores = val_scores[y_val == 1]
    threshold = np.percentile(normal_val_scores, 3.0)
    print(f"Selected Threshold for ~3% FPR: {threshold:.4f}")
    
    print("\n--- Final Evaluation on Untouched Test Set ---")
    test_scores = clf.decision_function(X_test)
    y_pred_test = np.where(test_scores < threshold, -1, 1)
    
    print("Isolation Forest Performance:")
    print(classification_report(y_test, y_pred_test, target_names=['Anomaly (-1)', 'Normal (1)']))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred_test))
    
    y_test_binary = np.where(y_test == -1, 1, 0)
    scores_binary = -test_scores
    auc = roc_auc_score(y_test_binary, scores_binary)
    print(f"ROC-AUC: {auc:.4f}")
    
    print("\n--- Rule-Based Detector Performance on Test Set ---")
    y_pred_rule = evaluate_rule_based(raw_test_windows)
    print(classification_report(y_test, y_pred_rule, target_names=['Anomaly (-1)', 'Normal (1)']))
    print("Confusion Matrix (Rule-Based):")
    print(confusion_matrix(y_test, y_pred_rule))
    
    # Save Model
    model_dir = os.path.join(PROJECT_ROOT, "app", "ml", "models")
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, "isolation_forest.joblib")
    model_data = {
        "model": clf,
        "threshold": float(threshold),
        "features": FEATURE_NAMES
    }
    
    joblib.dump(model_data, model_path)
    print(f"\nModel and threshold saved to {model_path}")

if __name__ == "__main__":
    main()
