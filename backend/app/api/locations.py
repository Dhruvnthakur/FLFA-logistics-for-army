from fastapi import APIRouter

from app.db import get_conn

router = APIRouter()


@router.get("/locations")
def locations():
    with get_conn() as conn:
        rows = conn.execute(
            "select id, name, kind, region, altitude_m, troop_strength, activity_level, st_asgeojson(geom)::json"
            " from locations order by kind, id"
        ).fetchall()
    keys = ["id", "name", "kind", "region", "altitude_m", "troop_strength", "activity_level"]
    return {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": r[-1], "properties": dict(zip(keys, r))} for r in rows],
    }
