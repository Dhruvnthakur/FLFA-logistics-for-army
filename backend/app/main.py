import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import dispatch, forecast, locations, routes, stock, whatif
from app.db import get_conn


@asynccontextmanager
async def lifespan(_):
    # migrations are idempotent; applying them here means a fresh Render deploy never serves without whatif_state
    with get_conn() as conn:
        for sql in sorted((Path(__file__).resolve().parents[2] / "db" / "migrations").glob("*.sql")):
            conn.execute(sql.read_text(encoding="utf-8"))
    yield


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
