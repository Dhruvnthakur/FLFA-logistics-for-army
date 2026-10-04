"""Synthetic network + 2 years of consumption. Pure functions, no DB.

All names and coordinates are fictional (plausible terrain only). Run directly for a self-check:
    python data/generator/generate.py
"""
import json
import math
import random
from pathlib import Path
from datetime import date, timedelta

SEED = 42
HISTORY_DAYS = 730
ROADS_FILE = Path(__file__).with_name("roads.json")

# id, name, kind, region, lat, lon, altitude_m, troop_strength, activity_level
# Names are fictional; coordinates are snapped to real roads (OSRM) and checked to lie inside India's border.
LOCATIONS = [
    ("BD1", "Base Depot North", "base_depot", "Northern Plains", 32.7499, 74.8500, 350, None, None),
    ("BD2", "Base Depot East", "base_depot", "Assam", 26.7000, 92.9518, 80, None, None),
    ("FD1", "Field Depot North", "field_depot", "Ladakh", 34.1499, 77.5504, 3500, None, None),
    ("FD2", "Field Depot East", "field_depot", "Arunachal", 27.5967, 93.6799, 1600, None, None),
    ("FD3", "Field Depot West", "field_depot", "Punjab", 31.5000, 74.9500, 230, None, None),
    ("P1", "Post 1", "post", "Ladakh", 34.4895, 77.7415, 4300, 80, 2),
    ("P2", "Post 2", "post", "Ladakh", 34.3330, 78.3092, 4600, 60, 2),
    ("P3", "Post 3", "post", "Ladakh", 33.9218, 78.2795, 4200, 120, 2),
    ("P4", "Post 4", "post", "Ladakh", 34.7309, 77.2180, 4800, 50, 3),
    ("P5", "Post 5", "post", "Ladakh", 33.3578, 78.3651, 3900, 150, 2),
    ("P6", "Post 6", "post", "Ladakh", 32.9488, 78.5985, 4500, 70, 1),
    ("P7", "Post 7", "post", "Ladakh", 33.5533, 78.6291, 5100, 90, 2),
    ("P8", "Post 8", "post", "Arunachal", 27.9000, 93.4001, 3800, 100, 2),
    ("P9", "Post 9", "post", "Arunachal", 27.9549, 93.1318, 4100, 70, 2),
    ("P10", "Post 10", "post", "Arunachal", 27.7859, 93.9213, 3300, 110, 1),
    ("P11", "Post 11", "post", "Punjab", 31.1996, 74.7000, 200, 120, 2),
    ("P12", "Post 12", "post", "Punjab", 31.8948, 74.8497, 230, 100, 2),
]

# id, name, class, unit, weight_kg_per_unit, priority  (priority 1 = most urgent)
ITEMS = [
    ("ammo", "Ammunition", "ammo", "boxes", 25, 1),
    ("medical", "Medical supplies", "medical", "kits", 5, 2),
    ("diesel", "Diesel", "fuel", "litres", 0.85, 3),
    ("rations", "Rations", "rations", "packs", 1.2, 4),
    ("spares", "Vehicle spares", "spares", "kits", 15, 5),
    ("winter_clothing", "Winter clothing", "clothing", "sets", 3, 6),
]

# Generator-only demand model: units per troop per day, activity sensitivity, cold sensitivity, surge-affected
DEMAND = {
    "ammo":            (0.02,  1.5, 0.00, True),
    "medical":         (0.01,  0.8, 0.00, True),
    "diesel":          (2.0,   0.5, 0.03, True),   # FR-16: cold → more fuel
    "rations":         (1.0,   0.1, 0.01, False),
    "spares":          (0.004, 0.6, 0.00, False),
    "winter_clothing": (0.003, 0.0, 0.08, False),
}

# id, name, from, to, terrain_difficulty (1-5), base_speed_kmh. Real road distance + geometry come from
# roads.json (python data/generator/fetch_roads.py). Speeds are convoy speeds and the demo's tuning knobs:
# Route A (direct, over the high pass) vs Route B (Indus valley via Post 5, then the rough track to Post 7) —
# slow enough that closing Route A adds ~2 days of lead time to Post 7 (the demo).
EDGES = [
    ("E1", "Northern Supply Line", "BD1", "FD1", 2, 40),
    ("E2", "Eastern Supply Line", "BD2", "FD2", 3, 30),
    ("E3", "FD1 - Post 1", "FD1", "P1", 3, 30),
    ("E4", "FD1 - Post 2", "FD1", "P2", 3, 28),
    ("E5", "FD1 - Post 3", "FD1", "P3", 3, 30),
    ("E6", "FD1 - Post 4", "FD1", "P4", 4, 22),
    ("E7", "Route B (leg 1)", "FD1", "P5", 2, 35),
    ("E8", "FD1 - Post 6", "FD1", "P6", 3, 30),
    ("E9", "Route A", "FD1", "P7", 5, 34),
    ("E10", "Route B (leg 2)", "P5", "P7", 4, 8),
    ("E11", "FD2 - Post 8", "FD2", "P8", 3, 28),
    ("E12", "FD2 - Post 9", "FD2", "P9", 4, 24),
    ("E13", "FD2 - Post 10", "FD2", "P10", 3, 30),
    ("E14", "Western Supply Line", "BD1", "FD3", 1, 45),
    ("E15", "FD3 - Post 11", "FD3", "P11", 1, 40),
    ("E16", "FD3 - Post 12", "FD3", "P12", 1, 40),
]

# id, type, capacity_t, depot_id
VEHICLES = [
    *[(f"V{i}", "Heavy truck", 10, "BD1") for i in range(1, 3)],
    *[(f"V{i}", "Heavy truck", 10, "BD2") for i in range(3, 5)],
    *[(f"V{i}", "Light truck", 2.5, "FD1") for i in range(5, 8)],
    *[(f"V{i}", "Medium truck", 5, "FD1") for i in range(8, 10)],
    *[(f"V{i}", "Light truck", 2.5, "FD2") for i in range(10, 12)],
    ("V12", "Medium truck", 5, "FD2"),
    *[(f"V{i}", "Light truck", 2.5, "FD3") for i in range(13, 15)],
]

DEMO_P7_DIESEL_DAYS = 12  # demo knob: start Green, simulator drains to Amber → Red


def point_wkt(lat, lon):
    return f"SRID=4326;POINT({lon} {lat})"


def load_roads():
    with open(ROADS_FILE, encoding="utf-8") as f:
        return json.load(f)


def edge_wkt(coords):
    return "SRID=4326;LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in coords) + ")"


def temperature(rng, region, altitude_m, day):
    mean = 25 - altitude_m / 1000 * 6.5
    amp = 12 if region == "Ladakh" else 8
    seasonal = -amp * math.cos(2 * math.pi * (day.timetuple().tm_yday - 15) / 365)  # coldest mid-Jan
    return round(mean + seasonal + rng.gauss(0, 3), 1)


def consumption(rng, end=None):
    """Daily rows: (post_id, item_id, date, qty, troop_strength, temp_c, activity_level)."""
    end = end or date.today() - timedelta(days=1)
    start = end - timedelta(days=HISTORY_DAYS - 1)
    rows = []
    for pid, _, kind, region, _, _, alt, base_troops, base_activity in LOCATIONS:
        if kind != "post":
            continue
        troops, activity, surge_days, surge_mult = base_troops, base_activity, 0, 1.0
        for n in range(HISTORY_DAYS):
            day = start + timedelta(days=n)
            if n % 90 == 0:  # troop rotation
                troops = round(base_troops * rng.uniform(0.8, 1.2))
            if n % 7 == 0 and rng.random() < 0.25:
                activity = rng.choices([1, 2, 3], weights=[3, 5, 2])[0]
            if surge_days == 0 and rng.random() < 0.01:
                surge_days, surge_mult = rng.randint(3, 7), rng.uniform(1.5, 2.5)
            surge = surge_mult if surge_days else 1.0
            surge_days = max(0, surge_days - 1)
            temp = temperature(rng, region, alt, day)
            for item, (rate, act_sens, cold_sens, surges) in DEMAND.items():
                qty = (troops * rate
                       * (1 + act_sens * (activity - 2) * 0.4)
                       * (1 + cold_sens * max(0.0, 10 - temp))
                       * (surge if surges else 1.0)
                       * max(0.0, rng.gauss(1, 0.1)))
                rows.append((pid, item, day, round(qty, 2), troops, temp, activity))
    return rows


def stock(rng, history):
    """(location_id, item_id, quantity, safety_stock) from the last 30 days of demand."""
    recent = {}
    cutoff = max(r[2] for r in history) - timedelta(days=29)
    for pid, item, day, qty, *_ in history:
        if day >= cutoff:
            recent[(pid, item)] = recent.get((pid, item), 0) + qty / 30

    rows = []
    for (pid, item), avg in recent.items():
        days = DEMO_P7_DIESEL_DAYS if (pid, item) == ("P7", "diesel") else rng.uniform(18, 35)
        # safety stock = 2 days: below every route lead time, so lead time (not the floor) decides Red
        rows.append((pid, item, round(avg * days, 1), round(avg * 2, 1)))

    region_of = {l[0]: l[3] for l in LOCATIONS}
    depots = {"BD1": None, "BD2": None, "FD1": "Ladakh", "FD2": "Arunachal", "FD3": "Punjab"}  # None = every post
    for depot, region in depots.items():
        for item, *_ in ITEMS:
            avg = sum(v for (pid, it), v in recent.items()
                      if it == item and (region is None or region_of[pid] == region))
            rows.append((depot, item, round(avg * 60, 1), round(avg * 15, 1)))
    return rows


def generate(seed=SEED, end=None):
    rng = random.Random(seed)
    roads = load_roads()
    locations = [(i, n, k, r, alt, t, a, point_wkt(lat, lon)) for i, n, k, r, lat, lon, alt, t, a in LOCATIONS]
    edges = [(i, n, a, b, roads[i]["distance_km"], t, v, edge_wkt(roads[i]["coords"])) for i, n, a, b, t, v in EDGES]
    history = consumption(rng, end)
    return {
        "locations": locations,
        "items": ITEMS,
        "route_edges": edges,
        "vehicles": VEHICLES,
        "consumption_history": history,
        "stock_levels": stock(rng, history),
    }


if __name__ == "__main__":
    d = generate()
    posts = [l for l in d["locations"] if l[2] == "post"]
    assert len(posts) == 12 and len(d["locations"]) == 17
    assert len(d["consumption_history"]) == 12 * len(ITEMS) * HISTORY_DAYS
    assert all(r[3] >= 0 for r in d["consumption_history"])
    names = {e[1] for e in d["route_edges"]}
    assert {"Route A", "Route B (leg 1)", "Route B (leg 2)"} <= names
    # every post reachable from a base depot
    adj = {}
    for _, _, a, b, *_ in d["route_edges"]:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    seen, todo = set(), ["BD1", "BD2"]
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo += adj.get(n, ())
    assert all(p[0] in seen for p in posts)
    # cold drives diesel: P7 January demand > July demand
    p7 = [r for r in d["consumption_history"] if r[0] == "P7" and r[1] == "diesel"]
    jan = sum(r[3] for r in p7 if r[2].month == 1) / sum(1 for r in p7 if r[2].month == 1)
    jul = sum(r[3] for r in p7 if r[2].month == 7) / sum(1 for r in p7 if r[2].month == 7)
    assert jan > jul, (jan, jul)
    assert len(d["stock_levels"]) == 17 * len(ITEMS)
    print(f"ok: {len(d['consumption_history'])} consumption rows; P7 diesel/day Jan {jan:.0f} L vs Jul {jul:.0f} L")
