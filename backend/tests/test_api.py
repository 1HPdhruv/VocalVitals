import pytest
import os
from fastapi.testclient import TestClient

# Use an in-memory test database
os.environ["DATABASE_URL"] = "sqlite:///./test_vocalvitals.db"

from main import app
from database import engine, Base
import models.user, models.session, models.baseline, models.model_version  # noqa: F401


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_and_login():
    # Register
    r = client.post("/auth/register", json={"email": "test@example.com", "password": "Pass1234"})
    assert r.status_code == 201
    assert r.json()["email"] == "test@example.com"

    # Login
    r = client.post("/auth/login", json={"email": "test@example.com", "password": "Pass1234"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    return token


def test_full_session_flow():
    # Must register first (each test gets a fresh DB)
    client.post("/auth/register", json={"email": "flow@example.com", "password": "Pass1234"})
    r = client.post("/auth/login", json={"email": "flow@example.com", "password": "Pass1234"})
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Save a cough session (should trigger baseline creation)
    r = client.post("/sessions", json={
        "prediction": "cough",
        "confidence": 0.92,
        "duration_ms": 1800,
        "features": [[0.1] * 16, [0.2] * 16],
    }, headers=headers)
    assert r.status_code == 201
    assert r.json()["prediction"] == "cough"


    # Baseline should now exist
    r = client.get("/baseline", headers=headers)
    assert r.status_code == 200
    assert r.json()["avg_confidence"] == pytest.approx(0.92)

    # List sessions
    r = client.get("/sessions", headers=headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    # Reset baseline
    r = client.put("/baseline/reset", headers=headers)
    assert r.status_code == 200

    # Baseline gone
    r = client.get("/baseline", headers=headers)
    assert r.status_code == 404
