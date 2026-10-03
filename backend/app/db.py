import os

import psycopg
from dotenv import load_dotenv

load_dotenv()  # local dev reads the repo-root .env; on Render the env vars are set directly


def get_conn():
    # ponytail: new connection per call; add psycopg_pool if request volume grows
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5)
