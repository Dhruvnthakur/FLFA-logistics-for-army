from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import forecast, locations, stock
from app.db import get_conn

app = FastAPI(title="Forward Logistics API")
app.include_router(locations.router)
app.include_router(forecast.router)
app.include_router(stock.router)

# ponytail: open CORS for dev; lock to the Vercel domain in Phase 8
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    try:
        with get_conn() as conn:
            postgis = conn.execute("select postgis_lib_version()").fetchone()[0]
        return {"status": "ok", "db": "ok", "postgis": postgis}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "db": str(e)})
