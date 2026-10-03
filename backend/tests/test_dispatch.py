import os
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from app.services.dispatch import assign, needs

os.environ["WEATHER_MODE"] = "sim"
c = TestClient(app)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
PATH = {"depot": "FD1", "nodes": ["FD1", "P7"], "edges": ["E9"], "edge_names": ["Route A"], "eta_hours": 6.0}


def stock_row(item, priority, dos, qty=0.0, demand=100.0):
    return {"kind": "post", "location_id": "P7", "location_name": "Post 7", "item_id": item,
            "item_name": item.title(), "unit": "units", "priority": priority, "quantity": qty,
            "daily_demand": demand, "days_of_supply": dos, "lead_time_days": 3.0}


def test_needs_ordered_by_priority_then_days_of_supply():
    rows = [stock_row("rations", 4, 1.0), stock_row("ammo", 1, 9.0), stock_row("medical", 2, 2.0),
            stock_row("diesel", 3, 0.5), stock_row("diesel2", 3, 0.2),
            stock_row("spares", 5, 30.0, qty=5000)]   # stocked well past lead + target → no need
    n = needs(rows, {r["item_id"]: 1.0 for r in rows}, {("P7", "ammo"): 300})
    assert [x["item_id"] for x in n] == ["ammo", "medical", "diesel2", "diesel", "rations"]
    assert n[0]["need"] == 100 * 13 - 300               # demand × (lead 3 + target 10) − committed


def test_ammo_and_medical_go_before_rations_when_capacity_is_short():
    rows = [stock_row("rations", 4, 0.5), stock_row("ammo", 1, 5.0), stock_row("medical", 2, 5.0)]
    n = needs(rows, {"rations": 1.0, "ammo": 1.0, "medical": 1.0}, {})   # 1300 units = 1.3 t each
    trucks = [{"id": "V1", "depot_id": "FD1", "free_t": 2.0, "dest": None},
              {"id": "V2", "depot_id": "FD1", "free_t": 0.6, "dest": None}]
    plan = assign(n, trucks, {("FD1", "P7"): PATH}, NOW)
    loaded = {(r["item_id"], r["vehicle_id"]): r["qty"] for r in plan}
    assert loaded[("ammo", "V1")] == 1300                     # most urgent class fills the biggest truck
    assert loaded[("medical", "V1")] == 700 and loaded[("medical", "V2")] == 600  # split across trucks
    assert loaded[("rations", None)] == 1300                  # rations left over despite lowest days-of-supply
    r = next(r for r in plan if r["vehicle_id"] == "V1")
    assert r["path"] == ["FD1", "P7"] and r["arrives_before_stockout"]
    assert "via Route A" in r["explanation"] and "before stock-out" in r["explanation"]


def test_unreachable_post_has_no_vehicle():
    n = needs([stock_row("ammo", 1, 1.0)], {"ammo": 1.0}, {})
    (r,) = assign(n, [{"id": "V1", "depot_id": "FD1", "free_t": 9, "dest": None}], {}, NOW)
    assert r["vehicle_id"] is None and r["origin"] is None and "no open route" in r["explanation"]


def p7_diesel():
    return [r for r in c.get("/dispatch-plan").json()["plan"] if (r["destination"], r["item_id"]) == ("P7", "diesel")]


def test_post7_diesel_plan_reroutes_when_route_a_closes_and_approval_sticks():
    with get_conn() as conn:
        manual0 = conn.execute("select status from route_edges where id = 'E9'").fetchone()[0]
        t0 = conn.execute("select now()").fetchone()[0]
        id0 = conn.execute("select coalesce(max(id), 0) from dispatch_plans").fetchone()[0]
    try:
        assert c.patch("/routes/E9", json={"status": "open"}).status_code == 200
        (before,) = p7_diesel()
        assert before["vehicle_id"] and before["edges"] == ["E9"] and before["eta"] and before["depart_by"]
        assert before["status"] == "proposed" and "via Route A" in before["explanation"]

        assert c.patch("/routes/E9", json={"status": "closed"}).status_code == 200
        (after,) = p7_diesel()
        assert after["edges"] == ["E7", "E10"] and after["eta"] > before["eta"]
        assert "Route B" in after["explanation"]

        assert c.patch(f"/dispatch-plan/{after['id']}", json={"status": "approved"}).status_code == 200
        (approved,) = p7_diesel()                       # committed qty covers the need → no duplicate row
        assert approved["id"] == after["id"] and approved["status"] == "approved"
        assert c.patch(f"/dispatch-plan/{after['id']}", json={"status": "approved"}).status_code == 409
        assert c.patch(f"/dispatch-plan/{after['id']}", json={"status": "dispatched"}).status_code == 200
    finally:
        with get_conn() as conn:
            conn.execute("update route_edges set status = %s where id = 'E9'", (manual0,))
            conn.execute("delete from alerts where created_at >= %s", (t0,))
            conn.execute("update alerts set resolved_at = null where resolved_at >= %s", (t0,))
            conn.execute("delete from dispatch_plans where id > %s and status <> 'proposed'", (id0,))


def test_dispatching_one_row_dispatches_the_whole_truck():
    with get_conn() as conn:
        id0 = conn.execute("select coalesce(max(id), 0) from dispatch_plans").fetchone()[0]
        ids = [r[0] for r in conn.execute(
            "insert into dispatch_plans (item_id, qty, vehicle_id, origin, destination, path, explanation)"
            " values ('ammo', 1, 'V12', 'FD2', 'P9', '{FD2,P9}', 't'), ('medical', 1, 'V12', 'FD2', 'P9',"
            " '{FD2,P9}', 't') returning id").fetchall()]
    try:
        r = c.patch(f"/dispatch-plan/{ids[0]}", json={"status": "dispatched"}).json()
        assert r["updated"] == sorted(ids)
    finally:
        with get_conn() as conn:
            conn.execute("delete from dispatch_plans where id > %s", (id0,))


def test_patch_dispatch_plan_validation():
    assert c.patch("/dispatch-plan/999999", json={"status": "approved"}).status_code == 404
    assert c.patch("/dispatch-plan/1", json={"status": "proposed"}).status_code == 422
