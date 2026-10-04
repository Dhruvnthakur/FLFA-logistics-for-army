"""Apply migrations, wipe all tables and reload synthetic data. Safe to re-run.

    python data/generator/seed.py      (backend venv active, DATABASE_URL in repo-root .env)
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from generate import generate

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

TABLES = ["whatif_state", "dispatch_plans", "alerts", "vehicles", "weather", "route_edges", "consumption_history",
          "stock_readings", "stock_levels", "items", "locations"]


def main():
    data = generate()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        for sql in sorted((ROOT / "db" / "migrations").glob("*.sql")):
            cur.execute(sql.read_text())
        cur.execute(f"truncate {', '.join(TABLES)} restart identity cascade")

        cur.executemany("insert into locations (id, name, kind, region, altitude_m, troop_strength, activity_level, geom)"
                        " values (%s, %s, %s, %s, %s, %s, %s, ST_GeogFromText(%s))", data["locations"])
        cur.executemany("insert into items (id, name, class, unit, weight_kg_per_unit, priority)"
                        " values (%s, %s, %s, %s, %s, %s)", data["items"])
        cur.executemany("insert into route_edges (id, name, from_node, to_node, distance_km, terrain_difficulty,"
                        " base_speed_kmh, geom) values (%s, %s, %s, %s, %s, %s, %s, ST_GeogFromText(%s))",
                        data["route_edges"])
        cur.executemany("insert into vehicles (id, type, capacity_t, depot_id) values (%s, %s, %s, %s)",
                        data["vehicles"])
        cur.executemany("insert into stock_levels (location_id, item_id, quantity, safety_stock)"
                        " values (%s, %s, %s, %s)", data["stock_levels"])
        with cur.copy("copy consumption_history (post_id, item_id, date, qty, troop_strength, temp_c, activity_level)"
                      " from stdin") as copy:
            for row in data["consumption_history"]:
                copy.write_row(row)

    print({k: len(v) for k, v in data.items()})


if __name__ == "__main__":
    main()
