"""Weather per node (FR-14): Open-Meteo when WEATHER_MODE=live, deterministic simulation otherwise.
Shape: {node_id: {"source", "temp_c", "days": [{"date", "snowfall_cm", "precip_mm", "wind_kmh"} × 3]}}."""
import json
import math
import os
import random
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
CACHE_SECONDS = 1800
RETRY_SECONDS = 300  # after a failed fetch, serve sim this long instead of re-timing-out every request
FORECAST_DAYS = 3

_live = {"at": 0.0, "data": None}  # ponytail: per-process cache; Open-Meteo updates hourly anyway


def nodes(conn):
    return conn.execute("select id, region, altitude_m, st_y(geom::geometry), st_x(geom::geometry)"
                        " from locations order by id").fetchall()


def simulated(rows, today=None):
    """Seasonal, altitude-driven and repeatable per node/day. Mild by design: it can degrade a road
    but never closes one — closures come from PATCH /routes or the what-if simulator."""
    today = today or date.today()
    out = {}
    for nid, region, alt, _, _ in rows:
        days = []
        for i in range(FORECAST_DAYS):
            d = today + timedelta(days=i)
            rng = random.Random(f"{nid}-{d}")
            amp = 12 if region == "Ladakh" else 8
            temp = 25 - alt / 1000 * 6.5 - amp * math.cos(2 * math.pi * (d.timetuple().tm_yday - 15) / 365) \
                + rng.gauss(0, 3)
            if i == 0:
                temp0 = temp
            days.append({"date": d.isoformat(),
                         "snowfall_cm": round(min(25.0, max(0.0, -temp) * rng.uniform(0, 1.2)), 1),
                         "precip_mm": round(rng.uniform(0, 15), 1),
                         "wind_kmh": round(min(70.0, 10 + alt / 200 + rng.uniform(0, 20)), 1)})
        out[nid] = {"source": "sim", "temp_c": round(temp0, 1), "days": days}
    return out


def live(rows):
    """One batched Open-Meteo call for every node."""
    q = urllib.parse.urlencode({
        "latitude": ",".join(str(r[3]) for r in rows), "longitude": ",".join(str(r[4]) for r in rows),
        "current": "temperature_2m", "daily": "snowfall_sum,precipitation_sum,wind_speed_10m_max",
        "forecast_days": FORECAST_DAYS, "timezone": "auto"})
    with urllib.request.urlopen(f"{OPEN_METEO}?{q}", timeout=10) as r:
        body = json.load(r)
    body = body if isinstance(body, list) else [body]  # a single location comes back unwrapped
    out = {}
    for (nid, *_), w in zip(rows, body):
        d = w["daily"]
        out[nid] = {"source": "live", "temp_c": w["current"]["temperature_2m"],
                    "days": [{"date": d["time"][i], "snowfall_cm": d["snowfall_sum"][i] or 0,
                              "precip_mm": d["precipitation_sum"][i] or 0, "wind_kmh": d["wind_speed_10m_max"][i] or 0}
                             for i in range(len(d["time"]))]}
    return out


def node_weather(conn):
    rows = nodes(conn)
    if os.environ.get("WEATHER_MODE", "sim") != "live":
        # ponytail: sim weather rolls over at midnight without resyncing alerts; the next reading or
        # route PATCH catches up. Resync here too if the demo ever runs across midnight.
        return simulated(rows)
    if _live["data"] is None or time.time() - _live["at"] > CACHE_SECONDS:
        try:
            _live.update(at=time.time(), data=live(rows))
        except Exception as e:  # offline / rate-limited → cache the sim fallback (FR-14), retry in RETRY_SECONDS
            print(f"Open-Meteo unavailable ({e}); using simulated weather")
            _live.update(at=time.time() - CACHE_SECONDS + RETRY_SECONDS, data=simulated(rows))
        from app.services.stock import resync_alerts  # local: stock → routing → weather would be circular
        resync_alerts(conn)  # new weather → new lead times → alerts must follow (cache is fresh, no recursion)
    return _live["data"]
