import os

from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from app.services.routing import risk_score, weather_status, worst

os.environ["WEATHER_MODE"] = "sim"  # deterministic; never hits Open-Meteo
c = TestClient(app)


def test_weather_rules():
    calm = {"snowfall_cm": 0, "precip_mm": 0, "wind_kmh": 10}
    assert weather_status(calm) == ("open", None)
    assert weather_status({**calm, "snowfall_cm": 12})[0] == "degraded"
    assert weather_status({**calm, "snowfall_cm": 12, "precip_mm": 60}) == ("closed", "precip_mm 60")
    assert worst("open", "degraded") == "degraded" and worst("closed", "open") == "closed"
    assert risk_score(5100, 5, "open") < risk_score(5100, 5, "degraded") <= 100


def p7():
    body = c.get("/routes").json()
    lead = next(s for s in c.get("/stock").json()["stock"] if (s["location_id"], s["item_id"]) == ("P7", "diesel"))
    return next(p for p in body["paths"] if p["post_id"] == "P7"), lead["lead_time_days"]


def test_closing_route_a_reroutes_post7_via_route_b():
    with get_conn() as conn:
        manual0 = conn.execute("select status from route_edges where id = 'E9'").fetchone()[0]
        t0 = conn.execute("select now()").fetchone()[0]  # DB clock: alerts are stamped by the DB
    try:
        assert c.patch("/routes/E9", json={"status": "open"}).status_code == 200
        before, lead_before = p7()
        assert before["edges"] == ["E9"], before                      # Route A direct
        assert c.patch("/routes/E9", json={"status": "closed"}).status_code == 200
        after, lead_after = p7()
        assert after["edges"] == ["E7", "E10"], after                 # Route B via Post 5
        assert after["eta_hours"] > before["eta_hours"] and lead_after > lead_before
        e9 = next(f for f in c.get("/routes").json()["features"] if f["properties"]["id"] == "E9")["properties"]
        assert e9["status"] == "closed" and e9["eta_hours"] is None
    finally:
        with get_conn() as conn:
            conn.execute("update route_edges set status = %s where id = 'E9'", (manual0,))
            conn.execute("delete from alerts where created_at >= %s", (t0,))
            conn.execute("update alerts set resolved_at = null where resolved_at >= %s", (t0,))


def test_patch_route_validation():
    assert c.patch("/routes/E9", json={"status": "flooded"}).status_code == 422
    assert c.patch("/routes/NOPE", json={"status": "closed"}).status_code == 404
