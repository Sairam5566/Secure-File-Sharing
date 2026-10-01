from typing import List, Dict, Any, Optional
from datetime import datetime, time
import zoneinfo

class LogRow:
    """A minimal protocol-like class for access log rows to make testing easy."""
    def __init__(self, user_id: Optional[int], access_time: datetime, 
                 access_status: str, action_type: str, file_id: Optional[int]):
        self.user_id = user_id
        self.access_time = access_time
        self.access_status = access_status
        self.action_type = action_type
        self.file_id = file_id

def is_off_hours(dt: datetime, tz_name: str = "Asia/Kolkata") -> bool:
    """Returns True if the time is outside standard business hours (e.g. 8AM to 6PM), or on weekends."""
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        
    local_dt = dt.astimezone(tz)
    
    # Weekend: Saturday(5), Sunday(6)
    if local_dt.weekday() >= 5:
        return True
    
    # Before 8 AM or after 6 PM (18:00)
    if local_dt.time() < time(8, 0) or local_dt.time() > time(18, 0):
        return True
    
    return False

def compute_user_features(logs: List[Any], current_time: datetime, window_minutes: int = 15) -> Dict[str, float]:
    """
    Computes per-user features over a sliding window for a single user's logs.
    Expects logs sorted by access_time.
    """
    # Safely skip logs with user_id None
    valid_logs = [log for log in logs if getattr(log, "user_id", None) is not None]
    
    if not valid_logs:
        return {
            "requests_per_minute": 0.0,
            "distinct_files": 0.0,
            "download_to_upload_ratio": 0.0,
            "failed_access_ratio": 0.0,
            "off_hours_activity": 0.0,
            "avg_time_between_requests": 0.0
        }

    # Filter logs within the window
    window_logs = [log for log in valid_logs if 0 <= (current_time - log.access_time).total_seconds() <= window_minutes * 60]
    
    num_logs = len(window_logs)
    if num_logs == 0:
        return {
            "requests_per_minute": 0.0,
            "distinct_files": 0.0,
            "download_to_upload_ratio": 0.0,
            "failed_access_ratio": 0.0,
            "off_hours_activity": 0.0,
            "avg_time_between_requests": 0.0
        }

    requests_per_minute = num_logs / max(1.0, float(window_minutes))
    
    distinct_files = set(log.file_id for log in window_logs if log.file_id is not None)
    
    num_downloads = sum(1 for log in window_logs if log.action_type == "download")
    num_uploads = sum(1 for log in window_logs if log.action_type == "upload")
    download_to_upload_ratio = float(num_downloads) / float(num_uploads) if num_uploads > 0 else float(num_downloads)

    num_failed = sum(1 for log in window_logs if log.access_status in ("denied", "failed_login", "failed"))
    failed_access_ratio = float(num_failed) / num_logs

    num_off_hours = sum(1 for log in window_logs if is_off_hours(log.access_time))
    off_hours_activity = float(num_off_hours) / num_logs

    # time between requests
    sorted_logs = sorted(window_logs, key=lambda x: x.access_time)
    if len(sorted_logs) > 1:
        time_diffs = [(sorted_logs[i].access_time - sorted_logs[i-1].access_time).total_seconds() for i in range(1, len(sorted_logs))]
        avg_time_between_requests = sum(time_diffs) / len(time_diffs)
    else:
        avg_time_between_requests = 0.0

    return {
        "requests_per_minute": requests_per_minute,
        "distinct_files": float(len(distinct_files)),
        "download_to_upload_ratio": download_to_upload_ratio,
        "failed_access_ratio": failed_access_ratio,
        "off_hours_activity": off_hours_activity,
        "avg_time_between_requests": avg_time_between_requests
    }
