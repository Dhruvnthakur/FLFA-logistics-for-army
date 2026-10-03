from fastapi.testclient import TestClient

from app.main import app
from app.services.forecasting import days_of_supply, explain


def test_days_of_supply_fixed_example():
    assert days_of_supply(25, [10, 10, 10]) == 2.5      # runs out inside the horizon
    assert days_of_supply(0, [10, 10]) == 0
    assert days_of_supply(50, [10, 10]) == 5.0           # beyond horizon: extrapolate at mean rate
    assert explain("Post 7", "Diesel", 4.04) == "Post 7 runs out of diesel in 4.0 days"


def test_forecast_endpoint_length_and_explanation():
    c = TestClient(app)
    r = c.get("/forecast/P7/diesel?days=10")
    assert r.status_code == 200
    body = r.json()
    assert len(body["forecast"]) == 10
    assert body["explanation"].startswith("Post 7 runs out of diesel in")
    assert c.get("/forecast/P7/nope").status_code == 404
    assert c.get("/forecast/P7/diesel?days=3").status_code == 422


def test_metrics_model_beats_baseline():
    m = TestClient(app).get("/forecast/metrics").json()
    assert m["overall_mape"]["model"] < m["overall_mape"]["baseline"]
