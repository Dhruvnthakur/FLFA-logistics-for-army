"""What-if simulator (FR-23, FR-24). Scenario state lives in whatif_state (db.get_state); routing and
forecasting read it, so applying a scenario is: save baseline → snapshot → mutate → resync → snapshot → diff."""
from app.db import get_state, set_state
from app.services import dispatch, routing, stock

STATUS_RANK = {"green": 0, "amber": 1, "red": 2}


def snapshot(conn, replan=True):
    """Posts' stock status + lead time, the plan's routes per post × item, and every route's effective status.
    replan=False reads the stored plan (the dashboard re-plans every 3 s, so it is current for a 'before')."""
    if replan:
        dispatch.replan(conn)
    es = routing.edges(conn)
    plan = dispatch.plan(conn)
    routes = {}
    for p in plan:
        if p["vehicle_id"] and p["status"] == "proposed":  # approved/dispatched convoys keep the route they left on
            routes.setdefault((p["destination"], p["item_id"]), set()).add(tuple(p["edges"]))
    return {"stock": {(s["location_id"], s["item_id"]): s for s in stock.all_stock(conn) if s["kind"] == "post"},
            "plan": {k: sorted(v) for k, v in routes.items()},
            "routes": {e["id"]: (e["name"], e["status"]) for e in es},
            "unassigned": {(p["destination"], p["item_id"]) for p in plan if not p["vehicle_id"]}}


def diff(before, after):
    """Two snapshots → what changed, in the shape the UI renders (FR-24)."""
    names = {i: n for i, (n, _) in after["routes"].items()}

    def line(k, b, a):
        return {"post_id": k[0], "post_name": a["location_name"], "item_id": k[1], "item_name": a["item_name"],
                "before": b["status"], "after": a["status"], "dos_before": b["days_of_supply"],
                "dos_after": a["days_of_supply"], "lead_before": b["lead_time_days"],
                "lead_after": a["lead_time_days"], "explanation": a["explanation"]}

    moved = [line(k, before["stock"][k], a) for k, a in after["stock"].items()
             if k in before["stock"] and before["stock"][k]["status"] != a["status"]]
    new_red = [m for m in moved if m["after"] == "red"]
    worse = [m for m in moved if STATUS_RANK[m["after"]] > STATUS_RANK[m["before"]] and m["after"] != "red"]
    better = [m for m in moved if STATUS_RANK[m["after"]] < STATUS_RANK[m["before"]]]

    def via(edge_sets):
        return " + ".join(dict.fromkeys(names.get(e, e) for es in edge_sets for e in es))

    rerouted = []
    for k, edges in after["plan"].items():
        old = before["plan"].get(k)
        if old and old != edges:
            lb, la = before["stock"][k]["lead_time_days"], after["stock"][k]["lead_time_days"]
            a = after["stock"][k]
            rerouted.append({"post_id": k[0], "post_name": a["location_name"], "item_id": k[1],
                             "item_name": a["item_name"], "before_via": via(old), "after_via": via(edges),
                             "lead_before": lb, "lead_after": la,
                             "delta_days": None if lb is None or la is None else round(la - lb, 1)})
    unassigned = [{"post_name": after["stock"][k]["location_name"], "item_name": after["stock"][k]["item_name"]}
                  for k in sorted(after["unassigned"] - before["unassigned"]) if k in after["stock"]]
    routes = [{"id": i, "name": n, "before": before["routes"][i][1], "after": s}
              for i, (n, s) in after["routes"].items() if i in before["routes"] and before["routes"][i][1] != s]
    parts = [m["explanation"] for m in new_red[:2]] + \
            [f"{r['post_name']} {r['item_name'].lower()} now via {r['after_via']}"
             + ("" if r["delta_days"] is None else f" ({r['delta_days']:+.1f} days)") for r in rerouted[:1]]
    return {"headline": ". ".join(parts) or "No change to stock status or the dispatch plan",
            "new_red": new_red, "worse": worse, "recovered": better, "rerouted": rerouted,
            "newly_unassigned": unassigned, "routes_changed": routes}


def label(sc):
    if sc["type"] == "close_route":
        return f"{sc['route_name']} set to {sc['status']}"
    if sc["type"] == "storm":
        return f"Storm over {sc['route_name']} ({sc['radius_km']:g} km)"
    return f"{sc['post_name']} strength {sc['strength']}"


def _name(conn, sql, arg, what):
    r = conn.execute(sql, (arg,)).fetchone()
    if r is None:
        raise LookupError(f"unknown {what}: {arg}")
    return r[0]


MAX_SCENARIOS = 10  # every stored storm costs a spatial join on each poll


class TooMany(Exception):
    pass


def apply(conn, sc):
    """sc: validated scenario dict {type, ...}. Returns {scenario, diff}. Scenarios stack until reset.
    Raises LookupError (unknown id) or TooMany."""
    dispatch.lock(conn)  # read-modify-write on whatif_state: one writer at a time, same lock as replan
    sc = dict(sc)
    if sc["type"] in ("close_route", "storm"):
        sc["route_name"] = _name(conn, "select name from route_edges where id = %s", sc["route_id"], "route")
    else:
        sc["post_name"] = _name(conn, "select name from locations where id = %s and kind = 'post'",
                                sc["post_id"], "post")
    scenarios = get_state(conn, "scenarios", [])
    if len(scenarios) >= MAX_SCENARIOS:
        raise TooMany(f"{MAX_SCENARIOS} scenarios already applied; reset to baseline first")
    before = snapshot(conn, replan=False)
    if sc["type"] == "close_route":
        # remember only what a scenario changed, so reset never undoes a manual PATCH /routes on another road
        base = get_state(conn, "baseline_routes", {})
        if sc["route_id"] not in base:
            base[sc["route_id"]] = conn.execute("select status from route_edges where id = %s",
                                                (sc["route_id"],)).fetchone()[0]
            set_state(conn, "baseline_routes", base)
        routing.set_manual_status(conn, sc["route_id"], sc["status"])
    elif sc["type"] == "storm":
        # centre 80% along the road: roads out of a depot overlap near it, so a mid-route storm would close them too
        lat, lon = conn.execute("select st_y(p), st_x(p) from (select st_lineinterpolatepoint(geom::geometry, 0.8) p"
                                " from route_edges where id = %s) t", (sc["route_id"],)).fetchone()
        storms = get_state(conn, "storms", [])
        storm = {"route_id": sc["route_id"], "lat": lat, "lon": lon, "radius_km": sc["radius_km"]}
        if storm not in storms:
            set_state(conn, "storms", [*storms, storm])
    else:
        set_state(conn, "troops", {**get_state(conn, "troops", {}), sc["post_id"]: sc["strength"]})
    set_state(conn, "scenarios", [*scenarios, {**sc, "label": label(sc)}])
    stock.resync_alerts(conn)
    return {"scenario": sc, "diff": diff(before, snapshot(conn))}


def active(conn):
    return get_state(conn, "scenarios", [])


def reset(conn):
    """Restore route statuses, drop storms and troop overrides. Approved/dispatched rows stay (commitments)."""
    dispatch.lock(conn)
    before = snapshot(conn, replan=False)
    for eid, st in get_state(conn, "baseline_routes", {}).items():
        routing.set_manual_status(conn, eid, st)
    for key in ("baseline_routes", "storms", "troops", "scenarios"):
        set_state(conn, key, None)
    stock.resync_alerts(conn)
    return {"diff": diff(before, snapshot(conn))}
