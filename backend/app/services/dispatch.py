"""Dispatch recommendation (FR-17 … FR-20): greedy priority load plan over available vehicles."""
import math
from datetime import timedelta

from app.services import routing
from app.services.stock import all_stock, lead_time_days

TARGET_DAYS = 10.0  # resupply to cover lead time + this many days of forecast demand


def needs(stock_rows, weights, committed):
    """Post stock rows → resupply needs, ordered by item priority then lowest days-of-supply (FR-18).
    weights: item → kg/unit. committed: (post, item) → qty already approved/dispatched."""
    out = []
    for s in stock_rows:
        if s["kind"] != "post" or s["daily_demand"] is None:
            continue
        lead = s["lead_time_days"] or 0.0  # unreachable post: still listed, flagged with no vehicle
        qty = math.ceil(s["daily_demand"] * (lead + TARGET_DAYS) - s["quantity"]
                        - committed.get((s["location_id"], s["item_id"]), 0))
        if qty > 0:
            out.append({**s, "need": qty, "kg_per_unit": weights[s["item_id"]]})
    return sorted(out, key=lambda n: (n["priority"], n["days_of_supply"]))


def assign(needs_, vehicles, paths, now):
    """Greedy: each need, most urgent first, goes to vehicles at the nearest depot (by route ETA) that can
    reach the post, splitting across vehicles by capacity. A vehicle serves one post per trip.
    vehicles: [{id, depot_id, free_t, dest}] (mutated). paths: (depot, post) → routing path.
    Whatever doesn't fit is returned with vehicle_id None."""
    rows = []
    for n in needs_:
        post, left = n["location_id"], n["need"]
        depots = sorted((p for (d, pid), p in paths.items() if pid == post), key=lambda p: p["eta_hours"])
        for p in depots:
            # trucks already heading to this post first (consolidate), then the smallest that takes the whole
            # need (keeps big trucks for big needs), then the biggest
            need_t = left * n["kg_per_unit"] / 1000
            fleet = sorted((v for v in vehicles if v["depot_id"] == p["depot"] and v["dest"] in (None, post)),
                           key=lambda v: (v["dest"] is None, v["free_t"] < need_t,
                                          v["free_t"] if v["free_t"] >= need_t else -v["free_t"]))
            for v in fleet:
                load = min(left, math.floor(v["free_t"] * 1000 / n["kg_per_unit"] + 1e-6))  # float residue
                if load <= 0:
                    continue
                v["free_t"] -= load * n["kg_per_unit"] / 1000
                v["dest"] = post
                rows.append(row(n, load, v["id"], p, now))
                left -= load
                if not left:
                    break
            if not left:
                break
        if left:
            rows.append(row(n, left, None, depots[0] if depots else None, now))
    return rows


def row(n, qty, vehicle_id, path, now):
    """One recommendation + its one-sentence explanation."""
    base = {"item_id": n["item_id"], "qty": qty, "vehicle_id": vehicle_id, "destination": n["location_id"],
            "origin": path["depot"] if path else None, "path": path["nodes"] if path else [],
            "edges": path["edges"] if path else []}
    what = f"{qty} {n['unit']} {n['item_name'].lower()} to {n['location_name']}"
    if path is None:
        return {**base, "depart_by": None, "eta": None, "arrives_before_stockout": False,
                "explanation": f"{what}: no open route"}
    lead = lead_time_days(path["eta_hours"])
    stockout = now + timedelta(days=n["days_of_supply"])
    eta = now + timedelta(days=lead)  # if it leaves now
    on_time = eta <= stockout
    via = ", ".join(dict.fromkeys(path["edge_names"]))
    if vehicle_id is None:
        msg = f"{what}: no vehicle free at any depot"
    else:
        margin = n["days_of_supply"] - lead
        msg = (f"Send {what} on {vehicle_id} from {path['depot']} via {via}; arrives in {lead:.1f} days, "
               + (f"{margin:.1f} days before stock-out" if on_time else f"{-margin:.1f} days AFTER stock-out"))
    return {**base, "depart_by": stockout - timedelta(days=lead), "eta": eta,
            "arrives_before_stockout": on_time, "explanation": msg}


COLS = ["item_id", "qty", "vehicle_id", "origin", "destination", "path", "edges", "depart_by", "eta",
        "arrives_before_stockout", "explanation"]


def lock(conn):
    """One writer to dispatch_plans at a time (replan vs replan, replan vs approve). Released at commit."""
    conn.execute("select pg_advisory_xact_lock(5005)")


def replan(conn):
    """Regenerate the proposed rows from current stock, routes and fleet (FR-18). Approved/dispatched rows are
    commitments: their qty counts as inbound and their trucks are spoken for. A proposed row keeps its id while
    (post, item, vehicle) stays the same, so an officer's Approve doesn't race the simulator."""
    lock(conn)
    now = conn.execute("select now()").fetchone()[0]
    es = routing.edges(conn)
    leads = {pid: lead_time_days(p["eta_hours"]) for pid, p in routing.best_paths(conn, es).items()}
    weights = {i: float(w) for i, w in conn.execute("select id, weight_kg_per_unit from items")}
    # ponytail: deliveries aren't simulated, so committed qty counts as inbound until re-seed; approved rows
    # also keep the path they were approved on (not re-routed if a road closes) — re-plan them if that matters
    committed = {(d, i): float(q) for d, i, q in conn.execute(
        "select destination, item_id, sum(qty) from dispatch_plans where status <> 'proposed' group by 1, 2")}
    loaded = {v: (d, float(t)) for v, d, t in conn.execute(
        "select p.vehicle_id, p.destination, sum(p.qty * i.weight_kg_per_unit) / 1000 from dispatch_plans p"
        " join items i on i.id = p.item_id where p.status = 'approved' group by 1, 2")}
    vehicles = [{"id": v, "depot_id": d, "free_t": float(cap) - loaded.get(v, (None, 0.0))[1],
                 "dest": loaded.get(v, (None,))[0]}
                for v, d, cap in conn.execute(
                    "select id, depot_id, capacity_t from vehicles where available and id not in"
                    " (select vehicle_id from dispatch_plans where status = 'dispatched' and vehicle_id is not null)"
                    " order by id")]
    rows = assign(needs(all_stock(conn, leads), weights, committed), vehicles, routing.depot_paths(conn, es), now)

    old = {(d, i, v): pid for pid, d, i, v in conn.execute(
        "select id, destination, item_id, vehicle_id from dispatch_plans where status = 'proposed'")}
    for r in rows:
        vals = [r[c] for c in COLS]
        pid = old.pop((r["destination"], r["item_id"], r["vehicle_id"]), None)
        if pid:
            conn.execute(f"update dispatch_plans set {', '.join(c + ' = %s' for c in COLS)} where id = %s",
                         (*vals, pid))
        else:
            conn.execute(f"insert into dispatch_plans ({', '.join(COLS)}) values ({', '.join(['%s'] * len(COLS))})",
                         vals)
    if old:
        conn.execute("delete from dispatch_plans where id = any(%s)", (list(old.values()),))


PLAN_SQL = """
select p.id, p.status, p.item_id, i.name, i.priority, p.qty, i.unit, p.vehicle_id, v.type, p.origin,
       p.destination, l.name, p.path, p.edges, p.depart_by, p.eta, p.arrives_before_stockout, p.explanation
from dispatch_plans p join items i on i.id = p.item_id join locations l on l.id = p.destination
left join vehicles v on v.id = p.vehicle_id
order by i.priority, p.eta nulls last, p.id
"""
PLAN_KEYS = ["id", "status", "item_id", "item_name", "priority", "qty", "unit", "vehicle_id", "vehicle_type",
             "origin", "destination", "destination_name", "path", "edges", "depart_by", "eta",
             "arrives_before_stockout", "explanation"]


def plan(conn):
    return [{**dict(zip(PLAN_KEYS, r)), "qty": float(r[5])} for r in conn.execute(PLAN_SQL).fetchall()]
