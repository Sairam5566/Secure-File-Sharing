"""
scripts/evaluate_anomaly_model.py
----------------------------------
Evaluate the SAVED model bundle (no retraining) against a fresh synthetic
test set whose seed differs from training (seed=42) and validation (seed=77).

Usage:
    python scripts/evaluate_anomaly_model.py
"""
import os
import sys
import random
import numpy as np
import joblib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
)

# ── project root on sys.path ─────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from app.ml.features import compute_user_features, LogRow
from app.ml.anomaly_detector import AnomalyDetector
from app.config import settings

# ── seeds ────────────────────────────────────────────────────────────────────
# training used seed 42, validation used 77 (implicitly from the same run).
# This evaluation uses seed 99 — a completely fresh draw.
EVAL_SEED = 99

FEATURE_NAMES = [
    "requests_per_minute",
    "distinct_files",
    "download_to_upload_ratio",
    "failed_access_ratio",
    "off_hours_activity",
    "avg_time_between_requests",
]

# ── raw-log generator (identical to train_anomaly_model.py) ──────────────────
def generate_raw_user_logs(user_id, user_type, end_time, window_minutes=15):
    """
    Generate raw AccessLog-like rows for one simulated user window.
    Mirrors the generator in train_anomaly_model.py exactly — same types,
    same probability distributions — so features are computed on real logs.
    """
    logs = []
    start_time = end_time - timedelta(minutes=window_minutes)

    if user_type == "normal_std":
        n_events = max(1, int(random.gammavariate(2.0, 0.5) * window_minutes))
        file_pool = [random.randint(1, 5) for _ in range(5)]
        dl_ul = 2.0
    elif user_type == "normal_bulk":
        n_events = max(5, int(random.gammavariate(5.0, 2.0) * window_minutes))
        file_pool = [random.randint(1, 50) for _ in range(20)]
        dl_ul = 5.0
    elif user_type == "normal_night":
        n_events = max(1, int(random.gammavariate(2.0, 1.0) * window_minutes))
        file_pool = [random.randint(1, 10) for _ in range(5)]
        dl_ul = 1.0
        end_time = end_time.replace(hour=2)
        start_time = end_time - timedelta(minutes=window_minutes)
    elif user_type == "anomaly_slow":
        n_events = int(random.gammavariate(10.0, 1.5) * window_minutes)
        file_pool = [random.randint(100, 150) for _ in range(30)]
        dl_ul = 20.0
    elif user_type == "anomaly_off":
        n_events = int(random.gammavariate(5.0, 2.0) * window_minutes)
        file_pool = [random.randint(200, 250) for _ in range(30)]
        dl_ul = 5.0
        end_time = end_time.replace(hour=3)
        start_time = end_time - timedelta(minutes=window_minutes)
    elif user_type == "anomaly_fail":
        n_events = max(5, int(random.gammavariate(3.0, 2.0) * window_minutes))
        file_pool = [random.randint(300, 305) for _ in range(2)]
        dl_ul = 1.0
    else:
        n_events, file_pool, dl_ul = 5, [1, 2], 1.0

    timestamps = sorted(
        start_time + timedelta(seconds=random.uniform(0, window_minutes * 60))
        for _ in range(n_events)
    )

    # Replicate the same-file clump for anomaly_slow
    if user_type == "anomaly_slow" and len(timestamps) >= 3 and random.random() < 0.5:
        mid = timestamps[len(timestamps) // 2]
        timestamps[0] = mid + timedelta(seconds=1)
        timestamps[1] = mid + timedelta(seconds=2)
        timestamps[2] = mid + timedelta(seconds=3)
        timestamps.sort()
        file_pool = [1000]
        dl_ul = 100.0

    for ts in timestamps:
        action = "download" if random.random() < (dl_ul / (dl_ul + 1)) else "upload"
        status = "granted"
        if user_type == "anomaly_fail":
            if random.random() < 0.80:
                status = "failed_login"
        else:
            if random.random() < 0.02:
                status = "denied"
        fid = random.choice(file_pool) if status != "failed_login" else None
        logs.append(
            LogRow(
                user_id=user_id,
                access_time=ts,
                access_status=status,
                action_type=action,
                file_id=fid,
            )
        )
    return logs


def build_dataset(user_types, current_time):
    """
    For each user type entry generate raw logs then compute features through
    the real compute_user_features pipeline.
    Returns (X: np.ndarray, raw_windows: list[list[LogRow]]).
    """
    X, raw_windows = [], []
    for i, u_type in enumerate(user_types):
        logs = generate_raw_user_logs(user_id=i, user_type=u_type, end_time=current_time)
        feats = compute_user_features(logs, current_time)
        X.append([feats[f] for f in FEATURE_NAMES])
        raw_windows.append(logs)
    return np.array(X), raw_windows


def evaluate_rule_based(raw_windows):
    """
    Run the real AnomalyDetector rule engine on each raw window.
    Rules (from anomaly_detector.py):
      - more than 10 events in 50 s  (burst)
      - >= 3 downloads of the same file in 10 s  (same-file repeat)
    A fresh detector is created per window so state does not leak between users.
    datetime.now(timezone.utc) is patched to the access_time of each event so the
    sliding-window logic inside the detector sees the correct simulated clock.
    """
    y_pred = []
    for logs in raw_windows:
        detector = AnomalyDetector()  # fresh per window -> no cross-contamination
        # Force the detector to use rule-based mode (no ML model needed here)
        detector.model = None
        flagged = False
        for log in logs:
            with patch("app.ml.anomaly_detector.datetime") as mock_dt:
                mock_dt.now.return_value = log.access_time.replace(tzinfo=timezone.utc)
                # db=None is fine because _fallback_rule_based does not use the DB
                is_anom, _ = detector.detect_anomaly(
                    None, log.user_id, log.file_id, log.action_type
                )
                if is_anom:
                    flagged = True
                    break
        y_pred.append(-1 if flagged else 1)
    return np.array(y_pred)


def print_metrics(label, y_true, y_pred, scores_for_auc=None):
    """Print a consistent metrics block."""
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[1, -1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    print(f"\n{'=' * 55}")
    print(f"  {label}")
    print(f"{'=' * 55}")
    print(classification_report(
        y_true, y_pred,
        labels=[-1, 1],
        target_names=["Anomaly (-1)", "Normal  (1)"],
        zero_division=0,
    ))
    print("Confusion matrix (rows=actual, cols=predicted):")
    print("              Pred Normal  Pred Anomaly")
    print(f"  Actual Normal    {tn:5d}        {fp:5d}")
    print(f"  Actual Anomaly   {fn:5d}        {tp:5d}")
    print(f"\nFalse-positive rate (FPR): {fpr:.4f}  ({fp} normal windows misclassified)")
    if scores_for_auc is not None:
        y_bin = (y_true == -1).astype(int)
        auc = roc_auc_score(y_bin, scores_for_auc)
        print(f"ROC-AUC:                   {auc:.4f}")


def main():
    # ── banner ────────────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print("  ML ANOMALY MODEL EVALUATION")
    print("  ** DATA IS SYNTHETIC — not from production **")
    print("=" * 55)
    print(f"  Evaluation seed : {EVAL_SEED} (training=42, validation=77)")
    print()

    # ── 1. Load saved bundle (no retraining) ─────────────────────────────────
    model_path = settings.MODEL_PATH
    print(f"Loading bundle from: {model_path}")
    if not os.path.exists(model_path):
        sys.exit(f"ERROR: model file not found at {model_path}. Run train_anomaly_model.py first.")

    bundle = joblib.load(model_path)
    for key in ("model", "threshold", "features"):
        if key not in bundle:
            sys.exit(f"ERROR: bundle is missing key '{key}'.")

    clf = bundle["model"]
    # threshold is stored as decision_function value (positive = normal side).
    # Inference uses: score = -decision_function -> anomalous when score > -threshold
    bundle_threshold = float(bundle["threshold"])
    features = bundle["features"]
    print(f"Bundle threshold (decision_function scale): {bundle_threshold:.6f}")
    print(f"Inference threshold (-score scale):         {-bundle_threshold:.6f}")
    print(f"Features ({len(features)}): {features}")

    # ── 2. Generate fresh test set (seed=99) ─────────────────────────────────
    random.seed(EVAL_SEED)
    np.random.seed(EVAL_SEED)

    current_time = datetime(2023, 10, 24, 15, 0, 0, tzinfo=timezone.utc)

    test_types = (
        ["normal_std"] * 1400
        + ["normal_bulk"] * 300
        + ["normal_night"] * 300
        + ["anomaly_slow"] * 80
        + ["anomaly_off"] * 60
        + ["anomaly_fail"] * 60
    )
    random.shuffle(test_types)

    n_normal = sum(1 for t in test_types if "anomaly" not in t)
    n_anomaly = sum(1 for t in test_types if "anomaly" in t)
    print(f"\nGenerating {len(test_types)} test windows "
          f"({n_normal} normal, {n_anomaly} anomaly) …")

    X_test, raw_windows = build_dataset(test_types, current_time)
    y_true = np.array([-1 if "anomaly" in t else 1 for t in test_types])

    print(f"Feature matrix shape: {X_test.shape}")

    # ── 3. ML model predictions ───────────────────────────────────────────────
    # Use the SAME sign convention as inference: score = -decision_function
    raw_scores = clf.decision_function(X_test)          # lower -> more anomalous
    anomaly_scores = -raw_scores                         # higher -> more anomalous
    y_pred_ml = np.where(raw_scores < bundle_threshold, -1, 1)

    print_metrics(
        "IsolationForest (saved bundle, seed=99 test set)",
        y_true,
        y_pred_ml,
        scores_for_auc=anomaly_scores,
    )

    # ── 4. Rule-based baseline ────────────────────────────────────────────────
    # Rules in AnomalyDetector._fallback_rule_based():
    #   burst  : > 10 events in 50 s
    #   repeat : >= 3 downloads of the same file in 10 s
    print("\nRunning rule-based detector on same windows …")
    print("  (fresh AnomalyDetector per window, datetime.now patched to event time)")
    y_pred_rule = evaluate_rule_based(raw_windows)

    print_metrics(
        "Rule-based detector (real AnomalyDetector rules)",
        y_true,
        y_pred_rule,
    )

    # ── 5. Side-by-side summary ───────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("  SUMMARY (positive class = Anomaly)")
    print("=" * 55)
    print(f"{'Metric':<28} {'ML model':>10} {'Rules':>10}")
    print("-" * 50)
    for metric, fn_name in [
        ("Precision (anomaly)", "precision_score"),
        ("Recall    (anomaly)", "recall_score"),
        ("F1        (anomaly)", "f1_score"),
    ]:
        fn = {"precision_score": precision_score,
              "recall_score": recall_score,
              "f1_score": f1_score}[fn_name]
        ml_val = fn(y_true, y_pred_ml, pos_label=-1, zero_division=0)
        rule_val = fn(y_true, y_pred_rule, pos_label=-1, zero_division=0)
        print(f"  {metric:<26} {ml_val:>10.4f} {rule_val:>10.4f}")

    tn_ml, fp_ml, fn_ml, tp_ml = confusion_matrix(y_true, y_pred_ml, labels=[1, -1]).ravel()
    tn_r,  fp_r,  fn_r,  tp_r  = confusion_matrix(y_true, y_pred_rule, labels=[1, -1]).ravel()
    fpr_ml   = fp_ml / (fp_ml + tn_ml) if (fp_ml + tn_ml) > 0 else 0.0
    fpr_rule = fp_r  / (fp_r  + tn_r ) if (fp_r  + tn_r ) > 0 else 0.0
    y_bin = (y_true == -1).astype(int)
    auc_ml = roc_auc_score(y_bin, anomaly_scores)
    print(f"  {'FPR':<26} {fpr_ml:>10.4f} {fpr_rule:>10.4f}")
    print(f"  {'ROC-AUC':<26} {auc_ml:>10.4f} {'N/A':>10}")
    print()
    print("NOTE: All data is SYNTHETIC. These numbers reflect the model's")
    print("      ability on simulated traffic, not real user behaviour.")
    print()


if __name__ == "__main__":
    main()
