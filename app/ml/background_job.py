import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import SessionLocal
from app.models import AccessLog
from app.ml.anomaly_detector import anomaly_detector
from app.ml.features import compute_user_features, LogRow
from app.config import settings

logger = logging.getLogger(__name__)

# Single instance of scheduler
scheduler = BackgroundScheduler()

def rescore_active_users():
    """
    Background job to re-score users active in the last 15 minutes.
    Uses a Postgres advisory lock (pg_try_advisory_lock) so that only one
    app instance or worker runs this at a time.

    Lock/unlock discipline:
    - A single 'db' connection is opened at the top and held for the entire job.
    - pg_try_advisory_lock(8888) is called on that same connection.
    - pg_advisory_unlock(8888) is called on that same connection in the finally
      block, but ONLY if the lock was actually acquired (lock_acquired is True).
    - If the lock was not acquired we return early; the finally block skips the
      unlock so we never release a lock we do not own.
    """
    db = SessionLocal()
    is_postgres = False
    lock_acquired = False
    try:
        is_postgres = db.bind.dialect.name == "postgresql"  # type: ignore
        if is_postgres:
            # Same connection holds the lock for the lifetime of this job run.
            lock_acquired = db.execute(
                text("SELECT pg_try_advisory_lock(8888)")
            ).scalar()
            if not lock_acquired:
                logger.debug(
                    "Anomaly rescoring job skipped: another instance holds lock 8888."
                )
                return  # finally runs, but lock_acquired=False → no unlock

        if anomaly_detector.model is None or anomaly_detector.ml_threshold is None or anomaly_detector.features is None:
            logger.info("ML model not fully loaded; skipping background rescoring job.")
            return

        now = datetime.now(timezone.utc)
        fifteen_mins_ago = now - timedelta(minutes=15)

        # 1. Find distinct users active in the last 15 minutes
        active_users = db.query(AccessLog.user_id).filter(
            AccessLog.access_time >= fifteen_mins_ago,
            AccessLog.user_id.isnot(None)
        ).distinct().all()

        active_user_ids = [row[0] for row in active_users]
        if not active_user_ids:
            logger.debug("No active users found for rescoring.")
            return

        logger.info(
            "Background rescoring: found %d active user(s) in the last 15 minutes.",
            len(active_user_ids),
        )

        # 2. Rescore each user
        for user_id in active_user_ids:
            user_logs = db.query(AccessLog).filter(
                AccessLog.user_id == user_id,
                AccessLog.access_time >= fifteen_mins_ago
            ).order_by(AccessLog.access_time.asc()).all()

            if not user_logs:
                continue

            # Convert to LogRow objects (normalise to UTC-aware datetimes)
            log_rows = []
            import typing
            for _log in user_logs:
                log = typing.cast(typing.Any, _log)
                dt = log.access_time
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                log_rows.append(
                    LogRow(
                        user_id=log.user_id,
                        access_time=dt,
                        access_status=log.access_status,
                        action_type=log.action_type,
                        file_id=log.file_id,
                    )
                )

            ad_features = anomaly_detector.features
            ad_model = anomaly_detector.model
            ad_threshold = anomaly_detector.ml_threshold
            
            if not ad_features or ad_model is None or ad_threshold is None:
                continue

            # Feature extraction via the same pipeline used at inference
            features_dict = compute_user_features(log_rows, current_time=now, window_minutes=15)
            feature_vector = [[features_dict[f] for f in ad_features]]

            # Score: higher value → more anomalous (−decision_function convention)
            raw_score = ad_model.decision_function(feature_vector)[0]
            score = -float(raw_score)
            is_anomalous = score > ad_threshold

            latest_log = typing.cast(typing.Any, user_logs[-1])

            update_needed = False

            # Fill in anomaly_score only if the inline check did not produce one.
            # Never overwrite a score that was already set by the inline scorer.
            if latest_log.anomaly_score is None:
                latest_log.anomaly_score = score
                update_needed = True

            # Never clear a flag that the inline check already set.
            # Only escalate: if the background job now flags and the row wasn't flagged.
            if is_anomalous and not latest_log.is_anomalous:
                latest_log.is_anomalous = True
                update_needed = True
                logger.warning(
                    "Background scorer flagged user %s (score=%.4f, threshold=%.4f).",
                    user_id, score, anomaly_detector.ml_threshold,
                )

            if update_needed:
                db.commit()

    except Exception as exc:
        logger.error("Background anomaly scoring job failed: %s", exc)
        db.rollback()
    finally:
        # Release the advisory lock ONLY if WE acquired it, on the SAME connection.
        if is_postgres and lock_acquired:
            try:
                db.execute(text("SELECT pg_advisory_unlock(8888)"))
                db.commit()
            except Exception as exc:
                logger.warning("Failed to release advisory lock 8888: %s", exc)
        db.close()


def start_background_jobs():
    if not scheduler.running:
        scheduler.add_job(
            rescore_active_users,
            "interval",
            minutes=settings.ANOMALY_JOB_INTERVAL_MINUTES,
            id="anomaly_rescoring_job",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            "Started background anomaly scoring job (interval: %dm).",
            settings.ANOMALY_JOB_INTERVAL_MINUTES,
        )


def stop_background_jobs():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Stopped background jobs.")
