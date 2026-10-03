from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_db_and_postgis():
    r = TestClient(app).get("/health")
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "ok"
