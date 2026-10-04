import json
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()  # local dev reads the repo-root .env; on Render the env vars are set directly


def get_conn():
    # ponytail: new connection per call; add psycopg_pool if request volume grows
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5)


def get_state(conn, key, default):
    """What-if scenario state (Phase 7): one jsonb value per key in whatif_state."""
    r = conn.execute("select value from whatif_state where key = %s", (key,)).fetchone()
    return default if r is None else r[0]


def set_state(conn, key, value):
    if value is None:
        conn.execute("delete from whatif_state where key = %s", (key,))
    else:
        conn.execute("insert into whatif_state (key, value) values (%s, %s::jsonb)"
                     " on conflict (key) do update set value = excluded.value", (key, json.dumps(value)))
