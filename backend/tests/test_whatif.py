import os

os.environ["WEATHER_MODE"] = "sim"  # before the app import: deterministic weather

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.whatif import MAX_SCENARIOS, diff  # noqa: E402

c = TestClient(app)


def reset():
    assert c.post("/whatif/reset").status_code == 200


def edge_status(eid):
    return next(f for f in c.get("/routes").json()["features"] if f["properties"]["id"] == eid)["properties"]["status"]


def p7_edges():
    return next(p for p in c.get("/routes").json()["paths"] if p["post_id"] == "P7")["edges"]


def test_storm_over_route_a_closes_it_and_reroutes_post7():
    reset()
    try:
        assert p7_edges() == ["E9"]
        r = c.post("/whatif", json={"type": "storm", "route_id": "E9"})
        assert r.status_code == 200, r.text
        assert edge_status("E9") == "closed" and edge_status("E10") != "closed"   # storm must not take Route B too
        assert p7_edges() == ["E7", "E10"]
        assert any(x["id"] == "E9" and x["after"] == "closed" for x in r.json()["diff"]["routes_changed"])
        assert c.get("/whatif").json()["active"][0]["label"].startswith("Storm over Route A")
    finally:
        reset()
    assert edge_status("E9") == "open" and p7_edges() == ["E9"] and c.get("/whatif").json()["active"] == []


def test_close_route_diff_shows_reroute_and_reset_restores():
    reset()
    try:
        d = c.post("/whatif", json={"type": "close_route", "route_id": "E1"}).json()["diff"]
        assert edge_status("E1") == "closed"
        assert d["routes_changed"] == [{"id": "E1", "name": "Northern Supply Line", "before": "open", "after": "closed"}]
        assert all(r["delta_days"] > 0 for r in d["rerouted"])   # on a fresh seed no convoy starts at BD1, so none may reroute
    finally:
        d = c.post("/whatif/reset").json()["diff"]
    assert edge_status("E1") == "open"
    assert any(r["id"] == "E1" and r["after"] == "open" for r in d["routes_changed"])


def test_troop_change_scales_demand_and_reset_restores():
    reset()

    def demand():
        s = next(s for s in c.get("/stock").json()["stock"] if (s["location_id"], s["item_id"]) == ("P7", "diesel"))
        return s["daily_demand"]

    base = demand()
    try:
        assert c.post("/whatif", json={"type": "troop_change", "post_id": "P7", "strength": 180}).status_code == 200
        assert abs(demand() - base * 2) < 0.02  # P7 holds 90 → 180 doubles forecast demand
    finally:
        reset()
    assert demand() == base


def test_validation():
    assert c.post("/whatif", json={"type": "storm", "route_id": "NOPE"}).status_code == 404
    assert c.post("/whatif", json={"type": "troop_change", "post_id": "FD1", "strength": 10}).status_code == 404
    assert c.post("/whatif", json={"type": "storm", "route_id": "E9", "radius_km": 500}).status_code == 422
    assert c.post("/whatif", json={"type": "troop_change", "post_id": "P7", "strength": 0}).status_code == 422
    assert c.post("/whatif", json={"type": "meteor"}).status_code == 422
    assert c.get("/whatif").json()["active"] == []        # rejected scenarios leave no state


def row(status, dos, lead):
    return {"location_name": "Post 7", "item_name": "Diesel", "status": status, "days_of_supply": dos,
            "lead_time_days": lead, "explanation": f"Post 7 runs out of diesel in {dos} days"}


def test_diff_pure():
    k = ("P7", "diesel")
    snap = lambda st, dos, lead, edges, rs: {  # noqa: E731
        "stock": {k: row(st, dos, lead)}, "plan": {k: [edges]}, "unassigned": set(),
        "routes": {"E9": ("Route A", rs), "E7": ("Route B (leg 1)", "open")}}
    d = diff(snap("amber", 4.0, 3.0, ("E9",), "open"), snap("red", 4.0, 4.6, ("E7",), "closed"))
    assert [m["item_id"] for m in d["new_red"]] == ["diesel"]
    assert d["rerouted"][0]["delta_days"] == 1.6 and d["rerouted"][0]["after_via"] == "Route B (leg 1)"
    assert d["routes_changed"] == [{"id": "E9", "name": "Route A", "before": "open", "after": "closed"}]
    assert "runs out of diesel" in d["headline"]
    same = snap("green", 9.0, 3.0, ("E9",), "open")
    assert diff(same, same)["headline"].startswith("No change")


def test_reset_keeps_manual_patch_and_stacked_scenarios_all_undo():
    reset()
    try:
        assert c.post("/whatif", json={"type": "close_route", "route_id": "E1"}).status_code == 200
        assert c.post("/whatif", json={"type": "storm", "route_id": "E9"}).status_code == 200
        assert c.post("/whatif", json={"type": "storm", "route_id": "E9"}).status_code == 200   # duplicate storm
        assert len(c.get("/whatif").json()["active"]) == 3
        assert c.patch("/routes/E5", json={"status": "closed"}).status_code == 200   # officer acts mid-scenario
    finally:
        reset()
        c.patch("/routes/E5", json={"status": "open"})
    assert edge_status("E1") == "open" and edge_status("E9") == "open"


def test_scenario_cap():
    reset()
    try:
        for _ in range(MAX_SCENARIOS):
            assert c.post("/whatif", json={"type": "storm", "route_id": "E9"}).status_code == 200
        assert c.post("/whatif", json={"type": "storm", "route_id": "E9"}).status_code == 409
    finally:
        reset()
