from fastapi.testclient import TestClient

from app.main import app


def test_locations_geojson_has_seeded_network():
    r = TestClient(app).get("/locations")
    assert r.status_code == 200
    features = r.json()["features"]
    kinds = [f["properties"]["kind"] for f in features]
    assert kinds.count("post") == 12 and len(features) == 17
    p7 = next(f for f in features if f["properties"]["id"] == "P7")
    assert p7["geometry"]["type"] == "Point"
