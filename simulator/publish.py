"""Simulated IoT stock feed (FR-7): each tick reads /stock, applies consumption + noise, POSTs /readings.

  python simulator/publish.py --api http://localhost:8000
  python simulator/publish.py --scenario drain-post7-diesel     # demo: P7 diesel Green → Amber → Red in ~1 min
  python simulator/publish.py --scenario ladakh-winter --ticks 5 # stress: every Ladakh post drains, FD1's fleet
                                                                 # runs out, overflow goes on BD1's long routes
Stdlib only, so it runs anywhere without the backend venv.
"""
import argparse
import json
import os
import random
import time
import urllib.request
from datetime import datetime, timezone

DRAIN = ("P7", "diesel")
DRAIN_DAYS_PER_TICK = 1.0  # demo scenario: Post 7 burns a whole day of diesel every tick
WINTER_POSTS = {f"P{i}" for i in range(1, 8)}  # Ladakh
WINTER_DAYS_PER_TICK = 3.0  # stress scenario: every Ladakh item burns 3 days per tick


def call(api, path, body=None):
    req = urllib.request.Request(api + path, method="POST" if body is not None else "GET",
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:  # first /stock call warms the forecast cache
        return json.load(r)


def next_readings(stock, sim_days, scenario, rng):
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for s in stock:
        q = s["quantity"]
        if s["daily_demand"]:  # posts consume; depots have no forecast and just report their level
            days = DRAIN_DAYS_PER_TICK if scenario == "drain-post7-diesel" and (s["location_id"], s["item_id"]) == DRAIN \
                else WINTER_DAYS_PER_TICK if scenario == "ladakh-winter" and s["location_id"] in WINTER_POSTS \
                else sim_days
            q = max(0.0, q - s["daily_demand"] * days * rng.uniform(0.8, 1.2))
        out.append({"location_id": s["location_id"], "item_id": s["item_id"], "quantity": round(q, 2), "timestamp": now})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=os.environ.get("API_URL", "http://localhost:8000"))
    p.add_argument("--interval", type=float, default=5, help="seconds between ticks")
    p.add_argument("--sim-hours", type=float, default=2, help="simulated consumption per tick for normal drift")
    p.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = forever)")
    p.add_argument("--scenario", choices=["normal", "drain-post7-diesel", "ladakh-winter"], default="normal")
    p.add_argument("--seed", type=int, default=None)
    a = p.parse_args()
    rng = random.Random(a.seed)
    tick = 0
    while not a.ticks or tick < a.ticks:
        tick += 1
        res = call(a.api, "/readings", next_readings(call(a.api, "/stock")["stock"], a.sim_hours / 24, a.scenario, rng))
        st = next(r for r in res["results"] if (r["location_id"], r["item_id"]) == DRAIN)
        reds = sum(r["status"] == "red" for r in res["results"])
        plan = call(a.api, "/dispatch-plan")["plan"]
        print(f"tick {tick}: {res['accepted']} readings | P7 diesel {st['status'].upper()}"
              f" ({st['days_of_supply']} days) | {reds} red | dispatch {len(plan)} rows,"
              f" {sum(r['vehicle_id'] is None for r in plan)} unassigned", flush=True)
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
