import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import dispatch, forecast, locations, routes, stock, whatif
from app.db import get_conn
from app.services.stock import all_stock


@asynccontextmanager
async def lifespan(_):
    # migrations are idempotent; applying them here means a fresh Render deploy never serves without whatif_state
    # ALTER TABLE takes an exclusive lock even when it is a no-op, so while the previous instance is still serving
    # (rolling deploy) it can wait out the statement timeout; give up fast and boot on the already-migrated schema
    try:
        with get_conn() as conn:
            conn.execute("set lock_timeout = '5s'")
            for sql in sorted((Path(__file__).resolve().parents[2] / "db" / "migrations").glob("*.sql")):
                conn.execute(sql.read_text(encoding="utf-8"))
    except (psycopg.errors.LockNotAvailable, psycopg.errors.QueryCanceled):
        logging.getLogger("uvicorn.error").warning("migrations skipped: lock wait timed out; assuming schema is current")
    threading.Thread(target=_warm_demand, daemon=True).start()
    yield


def _warm_demand():
    # the first /stock after boot fills the per-pair demand cache (minutes on Render's free CPU); do it in the background
    # so /health answers at once and the first dashboard poll is already warm
    try:
        with get_conn() as conn:
            all_stock(conn)
    except Exception:
        logging.getLogger("uvicorn.error").exception("demand warm-up failed")


app = FastAPI(title="Forward Logistics API", lifespan=lifespan)
app.include_router(locations.router)
app.include_router(forecast.router)
app.include_router(stock.router)
app.include_router(routes.router)
app.include_router(dispatch.router)
app.include_router(whatif.router)

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip().rstrip("/") for o in origins if o.strip()], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    try:
        with get_conn() as conn:
            postgis = conn.execute("select postgis_lib_version()").fetchone()[0]
        return {"status": "ok", "db": "ok", "postgis": postgis}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "db": str(e)})
