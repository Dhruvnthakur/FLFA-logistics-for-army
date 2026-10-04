"""One-off: real road distance + geometry for every edge from the public OSRM router → roads.json (committed).
Run by hand after changing LOCATIONS/EDGES; seeding never touches the network. Stdlib only.
    python data/generator/fetch_roads.py
"""
import json
import time
import urllib.request

from generate import EDGES, LOCATIONS, ROADS_FILE

OSRM = "https://router.project-osrm.org/route/v1/driving/"
SNAP_WARN_M = 2000  # a node this far from the nearest road is probably off-road — move it


def main():
    at = {l[0]: (l[4], l[5]) for l in LOCATIONS}
    out = {}
    for eid, name, a, b, _, _, *via in EDGES:
        pts = ";".join(f"{lon},{lat}" for lat, lon in [at[a], *via, at[b]])
        with urllib.request.urlopen(OSRM + pts + "?overview=simplified&geometries=geojson", timeout=30) as r:
            body = json.load(r)
        route = body["routes"][0]
        for n, w in zip((a, *via, b), body["waypoints"]):
            if w["distance"] > SNAP_WARN_M:
                print(f"WARN {eid}: {n} is {w['distance'] / 1000:.1f} km from the nearest road")
        coords = [[round(x, 5), round(y, 5)] for x, y in route["geometry"]["coordinates"]]
        out[eid] = {"distance_km": round(route["distance"] / 1000, 1), "coords": coords}
        print(f"{eid} {name}: {out[eid]['distance_km']} km, {len(coords)} points")
        time.sleep(1)  # public demo server: be polite
    ROADS_FILE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {ROADS_FILE}")


if __name__ == "__main__":
    main()
