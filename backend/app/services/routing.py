"""Route status, risk and best paths (FR-12, FR-13, FR-15). Plain functions over route_edges + weather."""
import networkx as nx

from app.services.weather import node_weather

LEVELS = ["open", "degraded", "closed"]
# today's value at either end of an edge: (degraded from, closed from)
RULES = {"snowfall_cm": (10, 30), "precip_mm": (20, 50), "wind_kmh": (50, 80)}  # precip → landslide risk
DEGRADED_SPEED = 0.5


def worst(*statuses):
    return max(statuses, key=LEVELS.index)


def weather_status(day):
    """One node-day of weather → open / degraded / closed, plus the reason."""
    st, why = "open", None
    for key, (deg, closed) in RULES.items():
        s = "closed" if day[key] >= closed else "degraded" if day[key] >= deg else "open"
        if LEVELS.index(s) > LEVELS.index(st):
            st, why = s, f"{key} {day[key]}"
    return st, why


def risk_score(max_alt, terrain, status):
    """0–100: altitude and terrain set the baseline, weather/manual degradation on top."""
    alt = min(25.0, max(0.0, (max_alt - 3000) / 100))
    return min(100, round(alt + terrain * 5 + {"open": 0, "degraded": 25, "closed": 50}[status]))


EDGE_SQL = """
select e.id, e.name, e.from_node, e.to_node, e.distance_km, e.terrain_difficulty, e.base_speed_kmh, e.status,
       greatest(a.altitude_m, b.altitude_m), st_asgeojson(e.geom)::json
from route_edges e join locations a on a.id = e.from_node join locations b on b.id = e.to_node
order by e.id
"""


def edges(conn):
    """Every edge with manual + weather status, effective status, risk and travel hours (None when closed)."""
    wx = node_weather(conn)
    out = []
    for eid, name, a, b, dist, terrain, speed, manual, alt, geom in conn.execute(EDGE_SQL).fetchall():
        node_st = [weather_status(wx[n]["days"][0]) for n in (a, b) if n in wx]
        w_st, why = max(node_st, key=lambda s: LEVELS.index(s[0]), default=("open", None))
        st = worst(manual, w_st)
        speed = float(speed) * (DEGRADED_SPEED if st == "degraded" else 1)
        out.append({"id": eid, "name": name, "from": a, "to": b, "distance_km": float(dist),
                    "terrain_difficulty": float(terrain), "manual_status": manual, "weather_status": w_st,
                    "weather_reason": why, "status": st, "risk": risk_score(alt, float(terrain), st),
                    "eta_hours": None if st == "closed" else round(float(dist) / speed, 2), "geom": geom})
    return out


def best_paths(conn, es=None):
    """Lowest-weight path from any depot to every post. weight = hours × (1 + risk/100); closed edges removed.
    Unreachable posts get reachable=False."""
    es = es if es is not None else edges(conn)
    g = nx.Graph()
    for e in es:
        if e["status"] != "closed":
            g.add_edge(e["from"], e["to"], weight=e["eta_hours"] * (1 + e["risk"] / 100), edge=e)
    locs = conn.execute("select id, kind from locations").fetchall()
    depots = [i for i, k in locs if k != "post" and i in g]
    dist, paths = nx.multi_source_dijkstra(g, depots) if depots else ({}, {})
    out = {}
    for pid in (i for i, k in locs if k == "post"):
        if pid not in paths:
            out[pid] = {"post_id": pid, "reachable": False, "depot": None, "nodes": [], "edges": [],
                        "eta_hours": None, "risk": None}
            continue
        nodes = paths[pid]
        legs = [g.edges[u, v]["edge"] for u, v in zip(nodes, nodes[1:])]
        out[pid] = {"post_id": pid, "reachable": True, "depot": nodes[0], "nodes": nodes,
                    "edges": [e["id"] for e in legs], "eta_hours": round(sum(e["eta_hours"] for e in legs), 2),
                    "risk": max(e["risk"] for e in legs)}
    return out


def set_manual_status(conn, edge_id, status):
    return conn.execute("update route_edges set status = %s where id = %s returning id",
                        (status, edge_id)).fetchone() is not None
