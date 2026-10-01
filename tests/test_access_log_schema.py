"""
Tests for the extended AccessLogResponse schema (is_anomalous, anomaly_score)
and the is_anomalous query filter on GET /access-logs/.

RBAC coverage:
  - regular users can ONLY see their own rows
  - admins can see all rows (and filter by user_id)
  - is_anomalous filter works correctly for both roles

Pattern note:
  SQLAlchemy will try to lazy-reload ORM-tracked attributes (e.g. .role)
  if the object is accessed after its originating session has closed.
  To avoid DetachedInstanceError we build plain (untracked) User objects
  whose attributes are already set in Python memory, so no DB round-trip
  is needed — exactly what test_route_inference.py does.
"""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app import models, auth


def _make_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session


def _plain_user(**kwargs) -> models.User:
    """Return a detachment-safe User with attributes already populated."""
    u = models.User(**kwargs)
    return u


class TestAccessLogFields(unittest.TestCase):
    """Verify is_anomalous and anomaly_score appear in GET /access-logs/ responses."""

    def setUp(self):
        Session = _make_session_factory()
        self._Session = Session

        def override_get_db():
            db = Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        # Build a plain user object (not tied to a session), then persist it
        # so the DB has a matching row for FK constraints.
        db = Session()
        db_user = models.User(
            username="alice", email="alice@test.com",
            hashed_password="pw", role="user"
        )
        db.add(db_user)
        db.commit()
        user_id = db_user.id

        normal_log = models.AccessLog(
            user_id=user_id,
            action_type="upload",
            access_status="granted",
            is_anomalous=False,
            anomaly_score=None,
        )
        anomalous_log = models.AccessLog(
            user_id=user_id,
            action_type="download",
            access_status="granted",
            is_anomalous=True,
            anomaly_score=0.87,
        )
        db.add_all([normal_log, anomalous_log])
        db.commit()
        db.close()

        # Create a plain (session-free) User so the dependency override never
        # needs a live session to read .role / .id
        self.user = _plain_user(
            id=user_id,
            username="alice", email="alice@test.com",
            hashed_password="pw", role="user"
        )

        app.dependency_overrides[auth.get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_response_includes_is_anomalous_and_score(self):
        """Every access-log row must now carry is_anomalous and anomaly_score."""
        resp = self.client.get("/access-logs/")
        self.assertEqual(resp.status_code, 200, resp.text)
        logs = resp.json()
        self.assertGreater(len(logs), 0)
        for log in logs:
            self.assertIn("is_anomalous", log, "is_anomalous missing from response")
            self.assertIn("anomaly_score", log, "anomaly_score missing from response")

    def test_filter_is_anomalous_true(self):
        """?is_anomalous=true should return only flagged rows."""
        resp = self.client.get("/access-logs/?is_anomalous=true")
        self.assertEqual(resp.status_code, 200, resp.text)
        logs = resp.json()
        self.assertGreater(len(logs), 0, "Expected at least one anomalous log")
        for log in logs:
            self.assertTrue(log["is_anomalous"], f"Non-anomalous row returned: {log}")

    def test_filter_is_anomalous_false(self):
        """?is_anomalous=false should return only normal rows."""
        resp = self.client.get("/access-logs/?is_anomalous=false")
        self.assertEqual(resp.status_code, 200, resp.text)
        logs = resp.json()
        self.assertGreater(len(logs), 0, "Expected at least one normal log")
        for log in logs:
            self.assertFalse(log["is_anomalous"], f"Anomalous row returned: {log}")

    def test_anomaly_score_value(self):
        """The anomalous row's anomaly_score must come back as 0.87."""
        resp = self.client.get("/access-logs/?is_anomalous=true")
        self.assertEqual(resp.status_code, 200, resp.text)
        anomalous = resp.json()
        self.assertEqual(len(anomalous), 1)
        self.assertAlmostEqual(anomalous[0]["anomaly_score"], 0.87, places=2)

    def test_normal_row_score_is_null(self):
        """Normal rows with no score must return anomaly_score as null."""
        resp = self.client.get("/access-logs/?is_anomalous=false")
        self.assertEqual(resp.status_code, 200, resp.text)
        normal = resp.json()
        self.assertEqual(len(normal), 1)
        self.assertIsNone(normal[0]["anomaly_score"])


class TestAccessLogRBAC(unittest.TestCase):
    """Verify RBAC: regular users see only their own rows; admins see all."""

    def setUp(self):
        Session = _make_session_factory()
        self._Session = Session

        def override_get_db():
            db = Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        db = Session()
        db_user_a = models.User(username="user_a", email="a@test.com",
                                hashed_password="pw", role="user")
        db_user_b = models.User(username="user_b", email="b@test.com",
                                hashed_password="pw", role="user")
        db_admin  = models.User(username="admin_u", email="admin@test.com",
                                hashed_password="pw", role="admin")
        db.add_all([db_user_a, db_user_b, db_admin])
        db.commit()

        # Capture IDs while session is open
        a_id    = db_user_a.id
        b_id    = db_user_b.id
        admin_id = db_admin.id

        db.add(models.AccessLog(
            user_id=a_id, action_type="upload",
            access_status="granted", is_anomalous=False,
        ))
        db.add(models.AccessLog(
            user_id=b_id, action_type="download",
            access_status="granted", is_anomalous=True, anomaly_score=0.5,
        ))
        db.commit()
        db.close()

        # Plain (detachment-safe) objects
        self.user_a = _plain_user(id=a_id, username="user_a", email="a@test.com",
                                  hashed_password="pw", role="user")
        self.user_b = _plain_user(id=b_id, username="user_b", email="b@test.com",
                                  hashed_password="pw", role="user")
        self.admin  = _plain_user(id=admin_id, username="admin_u", email="admin@test.com",
                                  hashed_password="pw", role="admin")

    def tearDown(self):
        app.dependency_overrides.clear()

    def _client_as(self, user: models.User) -> TestClient:
        app.dependency_overrides[auth.get_current_user] = lambda: user
        return TestClient(app)

    def test_regular_user_sees_only_own_logs(self):
        """user_a must not see user_b's log."""
        client = self._client_as(self.user_a)
        resp = client.get("/access-logs/")
        self.assertEqual(resp.status_code, 200, resp.text)
        logs = resp.json()
        for log in logs:
            self.assertEqual(
                log["user_id"], self.user_a.id,
                f"user_a received a log belonging to user_id={log['user_id']}"
            )

    def test_regular_user_cannot_filter_by_another_user_id(self):
        """Even if user_a passes ?user_id=<user_b.id>, they still see only their own rows."""
        client = self._client_as(self.user_a)
        resp = client.get(f"/access-logs/?user_id={self.user_b.id}")
        self.assertEqual(resp.status_code, 200, resp.text)
        logs = resp.json()
        for log in logs:
            self.assertEqual(log["user_id"], self.user_a.id)

    def test_admin_sees_all_logs(self):
        """Admin receives logs from all users."""
        client = self._client_as(self.admin)
        resp = client.get("/access-logs/")
        self.assertEqual(resp.status_code, 200, resp.text)
        logs = resp.json()
        user_ids = {log["user_id"] for log in logs}
        self.assertIn(self.user_a.id, user_ids, "Admin missing user_a's log")
        self.assertIn(self.user_b.id, user_ids, "Admin missing user_b's log")

    def test_admin_can_filter_by_user_id(self):
        """Admin can narrow down to a single user using ?user_id=."""
        client = self._client_as(self.admin)
        resp = client.get(f"/access-logs/?user_id={self.user_b.id}")
        self.assertEqual(resp.status_code, 200, resp.text)
        logs = resp.json()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["user_id"], self.user_b.id)

    def test_admin_is_anomalous_filter(self):
        """Admin can combine user_id filter with is_anomalous filter."""
        client = self._client_as(self.admin)
        resp = client.get(f"/access-logs/?user_id={self.user_b.id}&is_anomalous=true")
        self.assertEqual(resp.status_code, 200, resp.text)
        logs = resp.json()
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0]["is_anomalous"])
        self.assertAlmostEqual(logs[0]["anomaly_score"], 0.5, places=2)


if __name__ == "__main__":
    unittest.main()
