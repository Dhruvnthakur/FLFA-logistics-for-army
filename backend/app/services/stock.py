"""Stock status (FR-8) and alerts (FR-9). The ONLY place Green/Amber/Red thresholds live."""
from app.services.forecasting import days_of_supply, daily_demand, explain

# ponytail: flat lead time until Phase 4 replaces it with the best-route ETA per post
LEAD_TIME_DAYS = 3.0
BUFFER_DAYS = 4.0  # Amber band: lead time < days-of-supply < lead time + buffer


def status(qty, safety, dos, lead_time=LEAD_TIME_DAYS):
    """Red: below safety stock or runs out before resupply can land. Amber: inside the buffer. Else Green.
    dos is None for depots (no consumption forecast) → safety stock alone decides."""
    if qty < safety or (dos is not None and dos < lead_time):
        return "red"
    if dos is not None and dos < lead_time + BUFFER_DAYS:
        return "amber"
    return "green"


def thresholds():
    return {"lead_time_days": LEAD_TIME_DAYS, "buffer_days": BUFFER_DAYS,
            "red": "below safety stock, or days-of-supply < lead time",
            "amber": "days-of-supply < lead time + buffer"}


ROW_SQL = """
select s.location_id, l.name, l.kind, s.item_id, i.name, i.unit, i.priority,
       s.quantity, s.safety_stock, s.updated_at
from stock_levels s join locations l on l.id = s.location_id join items i on i.id = s.item_id
"""
ROW_KEYS = ["location_id", "location_name", "kind", "item_id", "item_name", "unit", "priority",
            "quantity", "safety_stock", "updated_at"]


def evaluate(conn, row):
    """Stock row dict → same dict plus days_of_supply, status, explanation."""
    qty, safety = float(row["quantity"]), float(row["safety_stock"])
    demand = daily_demand(conn, row["location_id"], row["item_id"]) if row["kind"] == "post" else None
    dos = days_of_supply(qty, demand[1]) if demand else None
    st = status(qty, safety, dos)
    if dos is not None:
        msg = explain(row["location_name"], row["item_name"], dos)
    else:
        msg = f"{row['location_name']} {row['item_name'].lower()} at {qty:.0f} {row['unit']}" \
              f" (safety stock {safety:.0f})"
    return {**row, "quantity": qty, "safety_stock": safety,
            "daily_demand": round(demand[1][0], 2) if demand else None,
            "days_of_supply": None if dos is None else round(dos, 1), "status": st, "explanation": msg}


def all_stock(conn):
    rows = conn.execute(ROW_SQL + " order by s.location_id, i.priority").fetchall()
    return [evaluate(conn, dict(zip(ROW_KEYS, r))) for r in rows]


def one_stock(conn, location_id, item_id):
    r = conn.execute(ROW_SQL + " where s.location_id = %s and s.item_id = %s", (location_id, item_id)).fetchone()
    return evaluate(conn, dict(zip(ROW_KEYS, r))) if r else None


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
