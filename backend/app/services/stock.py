"""Stock status (FR-8) and alerts (FR-9). The ONLY place Green/Amber/Red thresholds live."""
import math

from app.services import routing
from app.services.forecasting import days_of_supply, daily_demand, explain, troop_scale

HANDLING_DAYS = 2.0          # load, convoy clearance, unload — on top of driving time
DRIVING_HOURS_PER_DAY = 6.0  # high-altitude convoys move in daylight windows only
BUFFER_DAYS = 4.0            # Amber band: lead time < days-of-supply < lead time + buffer


def lead_time_days(eta_hours):
    """Best-route ETA → resupply lead time. No open route → infinite (nothing can land in time)."""
    return math.inf if eta_hours is None else HANDLING_DAYS + eta_hours / DRIVING_HOURS_PER_DAY


def lead_times(conn):
    return {pid: lead_time_days(p["eta_hours"]) for pid, p in routing.best_paths(conn).items()}


def status(qty, safety, dos, lead_time):
    """Red: below safety stock or runs out before resupply can land. Amber: inside the buffer. Else Green.
    dos is None for depots (no consumption forecast) → safety stock alone decides."""
    if qty < safety or (dos is not None and dos < lead_time):
        return "red"
    if dos is not None and dos < lead_time + BUFFER_DAYS:
        return "amber"
    return "green"


def thresholds():
    return {"handling_days": HANDLING_DAYS, "driving_hours_per_day": DRIVING_HOURS_PER_DAY,
            "buffer_days": BUFFER_DAYS,
            "lead_time": "handling days + best-route driving hours / driving hours per day",
            "red": "below safety stock, or days-of-supply < lead time",
            "amber": "days-of-supply < lead time + buffer"}


ROW_SQL = """
select s.location_id, l.name, l.kind, s.item_id, i.name, i.unit, i.priority,
       s.quantity, s.safety_stock, s.updated_at
from stock_levels s join locations l on l.id = s.location_id join items i on i.id = s.item_id
"""
ROW_KEYS = ["location_id", "location_name", "kind", "item_id", "item_name", "unit", "priority",
            "quantity", "safety_stock", "updated_at"]


def evaluate(conn, row, leads, scale=None):
    """Stock row dict → same dict plus days_of_supply, lead time, status, explanation.
    leads: post_id → lead time days (from lead_times)."""
    qty, safety = float(row["quantity"]), float(row["safety_stock"])
    demand = daily_demand(conn, row["location_id"], row["item_id"], scale) if row["kind"] == "post" else None
    dos = days_of_supply(qty, demand[1]) if demand else None
    lead = leads.get(row["location_id"]) if row["kind"] == "post" else None
    st = status(qty, safety, dos, lead if lead is not None else math.inf)
    if dos is not None:
        msg = explain(row["location_name"], row["item_name"], dos)
        msg += "; no open route to resupply" if lead == math.inf else f"; resupply takes {lead:.1f} days"
    else:
        msg = f"{row['location_name']} {row['item_name'].lower()} at {qty:.0f} {row['unit']}" \
              f" (safety stock {safety:.0f})"
    return {**row, "quantity": qty, "safety_stock": safety,
            "daily_demand": round(demand[1][0], 2) if demand else None,
            "days_of_supply": None if dos is None else round(dos, 1),
            "lead_time_days": None if lead is None or lead == math.inf else round(lead, 1),
            "status": st, "explanation": msg}


def all_stock(conn, leads=None):
    leads = leads if leads is not None else lead_times(conn)
    rows = conn.execute(ROW_SQL + " order by s.location_id, i.priority").fetchall()
    scale = troop_scale(conn)
    return [evaluate(conn, dict(zip(ROW_KEYS, r)), leads, scale) for r in rows]


def one_stock(conn, location_id, item_id, leads):
    r = conn.execute(ROW_SQL + " where s.location_id = %s and s.item_id = %s", (location_id, item_id)).fetchone()
    return evaluate(conn, dict(zip(ROW_KEYS, r)), leads) if r else None


def resync_alerts(conn):
    """Lead times changed (route closed / weather) → re-evaluate every row and raise/resolve alerts."""
    for s in all_stock(conn):
        sync_alert(conn, s)


def sync_alert(conn, s):
    """Raise on transition to Amber/Red, keep one open alert while the level persists, resolve on recovery."""
    open_ = conn.execute("select id, level from alerts where location_id = %s and item_id = %s"
                         " and resolved_at is null", (s["location_id"], s["item_id"])).fetchone()
    if open_ and open_[1] == s["status"]:
        return  # same condition persists → de-duplicated
    if open_:
        conn.execute("update alerts set resolved_at = now() where id = %s", (open_[0],))
    if s["status"] != "green":
        # partial unique index alerts_one_open backs this up against concurrent readings
        conn.execute("insert into alerts (location_id, item_id, level, message) values (%s, %s, %s, %s)"
                     " on conflict (location_id, item_id) where resolved_at is null do nothing",
                     (s["location_id"], s["item_id"], s["status"], s["explanation"]))


def open_alerts(conn):
    rows = conn.execute(
        "select a.id, a.location_id, l.name, a.item_id, i.name, i.priority, a.level, a.message, a.created_at"
        " from alerts a join locations l on l.id = a.location_id join items i on i.id = a.item_id"
        " where a.resolved_at is null order by a.level = 'red' desc, i.priority, a.created_at").fetchall()
    keys = ["id", "location_id", "location_name", "item_id", "item_name", "priority", "level", "message", "created_at"]
    return [dict(zip(keys, r)) for r in rows]
