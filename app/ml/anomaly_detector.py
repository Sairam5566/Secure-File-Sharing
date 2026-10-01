"""
Machine Learning Anomaly Detection Module
Uses Isolation Forest for detecting anomalous file access patterns
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app import models
from app.config import settings
from app.ml.features import compute_user_features, LogRow

logger = logging.getLogger(__name__)

try:
    import joblib  # type: ignore
except Exception:  # pragma: no cover
    joblib = None




class AnomalyDetector:
    """
    Sliding window anomaly detector for file access patterns.
    Loads ML model at startup, falls back to rules if missing.
    """

    def __init__(self, window_seconds: int = 50, threshold: int = 10):
        # Fallback rule state
        self.window_seconds = window_seconds
        self.threshold = threshold
        self._user_events: Dict[int, List[datetime]] = {}
        self._user_file_downloads: Dict[int, Dict[int, List[datetime]]] = {}
        self.same_file_window_seconds = 10
        self.same_file_threshold = 3
        
        # ML State
        self.model = None
        self.ml_threshold = None
        self.features = None
        self._load_model()

    def _load_model(self):
        """Load the IsolationForest model bundle from config path."""
        try:
            if joblib is None:
                logger.warning("joblib is not installed. ML model cannot be loaded. Falling back to rule-based detection.")
                return

            if not os.path.exists(settings.MODEL_PATH):
                logger.warning(f"Model file not found at {settings.MODEL_PATH}. Falling back to rule-based detection.")
                return
                
            bundle = joblib.load(settings.MODEL_PATH)
            if not all(k in bundle for k in ["model", "threshold", "features"]):
                logger.error("Corrupted model bundle: missing keys. Falling back to rule-based detection.")
                return
                
            self.model = bundle["model"]
            # Score convention: higher score = more anomalous
            # IsolationForest decision_function returns lower values for anomalies.
            # So score = -decision_function, and anomaly if score > -threshold
            self.ml_threshold = -float(bundle["threshold"])
            self.features = bundle["features"]
            logger.info("Anomaly detection ML model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load ML model: {str(e)}. Falling back to rule-based detection.")
            self.model = None

    def _fallback_rule_based(self, user_id: int, file_id: Optional[int], action_type: str) -> Tuple[bool, Optional[float]]:
        """
        Original rule-based fallback logic.
        Returns (is_anomalous, None) since rule-based doesn't have a model score.
        """
        now = datetime.now(timezone.utc)
        
        if user_id not in self._user_events:
            self._user_events[user_id] = []
            
        self._user_events[user_id].append(now)
        cutoff = now - timedelta(seconds=self.window_seconds)
        self._user_events[user_id] = [ts for ts in self._user_events[user_id] if ts > cutoff]
        event_count = len(self._user_events[user_id])
        
        if event_count > self.threshold:
            logger.warning(f"rule:burst - User {user_id} exceeded threshold.")
            return True, None
        
        if action_type == "download" and file_id is not None:
            if user_id not in self._user_file_downloads:
                self._user_file_downloads[user_id] = {}
            if file_id not in self._user_file_downloads[user_id]:
                self._user_file_downloads[user_id][file_id] = []
                
            self._user_file_downloads[user_id][file_id].append(now)
            file_cutoff = now - timedelta(seconds=self.same_file_window_seconds)
            self._user_file_downloads[user_id][file_id] = [
                ts for ts in self._user_file_downloads[user_id][file_id] if ts > file_cutoff
            ]
            
            if len(self._user_file_downloads[user_id][file_id]) >= self.same_file_threshold:
                logger.warning(f"rule:same_file - User {user_id} downloaded file {file_id} repeatedly.")
                return True, None
            
        return False, None

    def detect_anomaly(
        self, 
        db: Session, 
        user_id: Optional[int], 
        file_id: Optional[int], 
        action_type: str, 
        access_status: str = "granted"
    ) -> Tuple[bool, Optional[float]]:
        """
        Evaluate anomaly status for a new event.
        Never blocks/raises exceptions. Returns (is_anomalous, anomaly_score).
        """
        if user_id is None:
            # We skip scoring for anonymous/unknown users
            return False, None

        ml_threshold = self.ml_threshold
        features = self.features
        
        if not self.model or ml_threshold is None or features is None:
            return self._fallback_rule_based(user_id, file_id, action_type)
            
        try:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(minutes=15)
            
            # Fetch recent logs from DB
            db_logs = db.query(models.AccessLog).filter(
                models.AccessLog.user_id == user_id,
                models.AccessLog.access_time >= cutoff
            ).all()
            
            # Convert to LogRow objects
            logs = []
            for log in db_logs:
                # Extract actual datetime value from SQLAlchemy attribute
                acc_time: Any = getattr(log, "access_time")
                if acc_time.tzinfo is None:
                    acc_time = acc_time.replace(tzinfo=timezone.utc)
                    
                u_id: Any = getattr(log, "user_id")
                a_status: Any = getattr(log, "access_status")
                a_type: Any = getattr(log, "action_type")
                f_id: Any = getattr(log, "file_id")
                    
                logs.append(
                    LogRow(
                        user_id=int(u_id) if u_id is not None else None,
                        access_time=acc_time,
                        access_status=str(a_status),
                        action_type=str(a_type),
                        file_id=int(f_id) if f_id is not None else None
                    )
                )
            
            # Add the CURRENT event that hasn't been saved yet
            logs.append(
                LogRow(
                    user_id=user_id,
                    access_time=now,
                    access_status=access_status,
                    action_type=action_type,
                    file_id=file_id
                )
            )
            
            # Compute features
            features_dict = compute_user_features(logs, current_time=now, window_minutes=15)
            feature_vector = [[features_dict[f] for f in features]]
            
            # Score
            raw_score = self.model.decision_function(feature_vector)[0]
            # Convention: higher score = more anomalous
            score = -float(raw_score)
            
            is_anomalous = score > ml_threshold
            if is_anomalous:
                logger.warning(f"model_score - User {user_id} flagged by ML model. Score: {score:.4f}, Threshold: {ml_threshold:.4f}")
                
            return is_anomalous, score
            
        except Exception as e:
            logger.error(f"Scoring error: {str(e)}. Falling back to rules.")
            return self._fallback_rule_based(user_id, file_id, action_type)


# Global instance
anomaly_detector = AnomalyDetector()
