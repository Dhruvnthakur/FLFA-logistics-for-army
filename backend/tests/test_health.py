from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_db_and_postgis():
    r = TestClient(app).get("/health")
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "ok"


def test_cors_allows_listed_origin_only():
    c = TestClient(app)
    ok = c.get("/health", headers={"Origin": "http://localhost:5173"})
    bad = c.get("/health", headers={"Origin": "https://evil.example"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers
