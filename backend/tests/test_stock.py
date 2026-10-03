from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from app.services.forecasting import daily_demand
from app.services.stock import BUFFER_DAYS, HANDLING_DAYS, lead_time_days, status

c = TestClient(app)


def test_status_thresholds():
    lt = 3.0
    amber_top = lt + BUFFER_DAYS
    assert status(100, 10, amber_top + 1, lt) == "green"
    assert status(100, 10, amber_top - 0.1, lt) == "amber"
    assert status(100, 10, lt - 0.1, lt) == "red"          # runs out before resupply lands
    assert status(5, 10, amber_top + 10, lt) == "red"      # below safety stock wins over a healthy forecast
    assert status(100, 10, None, lt) == "green"            # depot: no forecast, safety stock decides
    assert status(5, 10, None, lt) == "red"
    assert status(100, 10, 365, lead_time_days(None)) == "red"  # no open route: nothing lands in time
    assert lead_time_days(0) == HANDLING_DAYS


def reading(qty, **kw):
    return {"location_id": "P7", "item_id": "diesel", "quantity": qty,
            "timestamp": datetime.now(timezone.utc).isoformat(), **kw}


def p7_alerts():
    return [a for a in c.get("/alerts").json()["alerts"] if (a["location_id"], a["item_id"]) == ("P7", "diesel")]


def test_alert_transitions_and_dedup():
    with get_conn() as conn:
        qty0, ts0 = conn.execute("select quantity, updated_at from stock_levels"
                                 " where location_id = 'P7' and item_id = 'diesel'").fetchone()
        daily = daily_demand(conn, "P7", "diesel")[1]
        conn.execute("update alerts set resolved_at = now() where location_id = 'P7' and item_id = 'diesel'"
                     " and resolved_at is null")
        db_t0 = conn.execute("select now()").fetchone()[0]  # alerts are stamped by the DB clock
    t0 = datetime.now(timezone.utc)  # readings are stamped by this test's clock
    lead = next(s for s in c.get("/stock").json()["stock"]
                if (s["location_id"], s["item_id"]) == ("P7", "diesel"))["lead_time_days"]
    mid = lead + BUFFER_DAYS / 2  # middle of the Amber band
    amber_qty = sum(daily[:int(mid)]) + daily[int(mid)] * (mid % 1)
    try:
        r = c.post("/readings", json=reading(amber_qty)).json()["results"][0]
        assert r["status"] == "amber", r
        first = p7_alerts()
        assert [a["level"] for a in first] == ["amber"]

        c.post("/readings", json=[reading(amber_qty * 0.99)])        # still Amber → no duplicate
        assert [a["id"] for a in p7_alerts()] == [first[0]["id"]]

        assert c.post("/readings", json=reading(0)).json()["results"][0]["status"] == "red"
        red = p7_alerts()
        assert [a["level"] for a in red] == ["red"] and red[0]["id"] != first[0]["id"]
        assert "Post 7 runs out of diesel in" in red[0]["message"]

        c.post("/readings", json=reading(sum(daily[:20])))            # restocked → resolved
        assert p7_alerts() == []
    finally:
        with get_conn() as conn:
            conn.execute("update stock_levels set quantity = %s, updated_at = %s"
                         " where location_id = 'P7' and item_id = 'diesel'", (qty0, ts0))
            conn.execute("delete from alerts where location_id = 'P7' and item_id = 'diesel' and created_at >= %s", (db_t0,))
            conn.execute("delete from stock_readings where location_id = 'P7' and item_id = 'diesel' and ts >= %s", (t0,))


def test_readings_validation():
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    for bad in (reading(-1), reading(5, location_id="P999"), reading(5, item_id="caviar"),
                reading(5, timestamp=future), reading(5, timestamp=old),
                reading(5, timestamp="2026-10-03T10:00:00"), []):          # naive ts, empty batch
        assert c.post("/readings", json=bad).status_code == 422, bad


def test_stock_serves_status_and_thresholds():
    body = c.get("/stock").json()
    assert body["thresholds"]["handling_days"] == HANDLING_DAYS
    p7 = next(s for s in body["stock"] if (s["location_id"], s["item_id"]) == ("P7", "diesel"))
    assert p7["status"] in ("green", "amber", "red") and p7["days_of_supply"] > 0
    assert p7["lead_time_days"] > HANDLING_DAYS and "resupply takes" in p7["explanation"]
    assert len(body["stock"]) == 78
