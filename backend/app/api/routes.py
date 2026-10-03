import os
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_conn
from app.services import routing, stock

router = APIRouter()


@router.get("/routes")
def get_routes():
    """FR-11/12/13: edges as GeoJSON (status, ETA, risk) + best depot → post path for every post."""
    with get_conn() as conn:
        es = routing.edges(conn)
        paths = routing.best_paths(conn, es)
    return {
        "type": "FeatureCollection",
        "weather_mode": os.environ.get("WEATHER_MODE", "sim"),
        "features": [{"type": "Feature", "geometry": e.pop("geom"), "properties": e} for e in es],
        "paths": list(paths.values()),
    }


class RouteStatus(BaseModel):
    status: Literal["open", "degraded", "closed"]


@router.patch("/routes/{edge_id}")
def patch_route(edge_id: str, body: RouteStatus):
    """Manual override; effective status = worse of this and the weather rule. Re-evaluates stock alerts."""
    with get_conn() as conn:
        if not routing.set_manual_status(conn, edge_id, body.status):
            raise HTTPException(404, f"unknown route: {edge_id}")
        stock.resync_alerts(conn)
    return {"id": edge_id, "manual_status": body.status}
