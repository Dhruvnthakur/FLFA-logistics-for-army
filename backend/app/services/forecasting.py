"""Demand forecasting: features, training, recursive forecast, days-of-supply.

One gradient-boosting model per item (all posts pooled). Lag/rolling features carry each post's scale.
Future troops/activity are held at their last value; future temperature is the post's seasonal mean.
"""
import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ARTIFACTS = Path(__file__).resolve().parents[2] / "ml" / "artifacts"
FEATURES = ["lag1", "lag7", "lag14", "roll7", "roll14", "doy_sin", "doy_cos", "troops", "temp", "activity"]
HOLDOUT_DAYS = 60
EVAL_HORIZON = 7
COLS = ["date", "qty", "troop_strength", "temp_c", "activity_level"]


def build_features(df):
    """df: one post × item, sorted by date, columns COLS. Features for day t only use qty up to t-1."""
    q = df["qty"]
    doy = pd.to_datetime(df["date"]).dt.dayofyear
    return pd.DataFrame({
        "lag1": q.shift(1), "lag7": q.shift(7), "lag14": q.shift(14),
        "roll7": q.shift(1).rolling(7).mean(), "roll14": q.shift(1).rolling(14).mean(),
        "doy_sin": np.sin(2 * np.pi * doy / 365), "doy_cos": np.cos(2 * np.pi * doy / 365),
        "troops": df["troop_strength"], "temp": df["temp_c"], "activity": df["activity_level"],
    })


def seasonal_temp(df):
    """Mean temperature per day-of-year from history — stand-in for a weather forecast."""
    return df.groupby(pd.to_datetime(df["date"]).dt.dayofyear)["temp_c"].mean().to_dict()


def forecast_series(model, hist, days, temp_by_doy):
    """Recursive N-day forecast. hist: one post × item, sorted, columns COLS."""
    h = hist.tail(30).reset_index(drop=True)
    last = h.iloc[-1]
    preds = []
    for i in range(1, days + 1):
        d = last["date"] + timedelta(days=i)
        row = {"date": d, "qty": np.nan, "troop_strength": last["troop_strength"],
               "temp_c": temp_by_doy.get(d.timetuple().tm_yday, last["temp_c"]),
               "activity_level": last["activity_level"]}
        h = pd.concat([h, pd.DataFrame([row])], ignore_index=True)
        p = max(0.0, float(model.predict(build_features(h).iloc[[-1]][FEATURES])[0]))
        h.loc[h.index[-1], "qty"] = p
        preds.append(p)
    return preds


def days_of_supply(stock, daily):
    """Days until stock hits zero given daily demand; beyond the horizon, extrapolate at the mean rate."""
    left = float(stock)
    for i, q in enumerate(daily):
        if q >= left:
            return i + (left / q if q else 0.0)
        left -= q
    return len(daily) + left / max(sum(daily) / len(daily), 1e-9)


def explain(post_name, item_name, dos):
    return f"{post_name} runs out of {item_name.lower()} in {dos:.1f} days"


def _fit(frames):
    X = pd.concat([build_features(f) for f in frames])
    y = pd.concat([f["qty"] for f in frames])
    ok = X.notna().all(axis=1)
    return HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, random_state=0).fit(X[ok], y[ok])


def train(df):
    """df: consumption_history rows (post_id, item_id, + COLS). Returns (models by item, metrics)."""
    df = df.sort_values("date")
    cutoff = df["date"].max() - timedelta(days=HOLDOUT_DAYS)
    groups = {k: g[COLS].reset_index(drop=True) for k, g in df.groupby(["item_id", "post_id"])}
    temps = {k: seasonal_temp(g) for k, g in groups.items()}
    errs = {}  # item -> {"model": [(abs_err, actual)], "baseline": [...]}
    models = {}
    for item in sorted(df["item_id"].unique()):
        keys = [k for k in groups if k[0] == item]
        trial = _fit([groups[k][groups[k]["date"] <= cutoff] for k in keys])
        for k in keys:
            g = groups[k]
            for origin in pd.date_range(cutoff, periods=HOLDOUT_DAYS // EVAL_HORIZON, freq=f"{EVAL_HORIZON}D"):
                hist = g[g["date"] <= origin.date()]
                actual = g[g["date"] > origin.date()].head(EVAL_HORIZON)["qty"].to_numpy()
                if len(actual) < EVAL_HORIZON:
                    continue
                pred = forecast_series(trial, hist, EVAL_HORIZON, temps[k])
                base = [hist["qty"].tail(7).mean()] * EVAL_HORIZON
                for name, p in (("model", pred), ("baseline", base)):
                    errs.setdefault(item, {}).setdefault(name, []).extend(zip(np.abs(np.array(p) - actual), actual))
        models[item] = _fit([groups[k] for k in keys])  # ship the model refit on all data

    def score(pairs):
        e, a = np.array(pairs).T
        return {"mae": round(float(e.mean()), 3), "mape": round(float((e / a).mean() * 100), 2)}

    metrics = {"holdout_days": HOLDOUT_DAYS, "horizon_days": EVAL_HORIZON,
               "per_item": {i: {n: score(p) for n, p in v.items()} for i, v in errs.items()}}
    for name in ("model", "baseline"):  # MAE isn't comparable across units, so overall is MAPE only
        allp = [p for v in errs.values() for p in v[name]]
        metrics.setdefault("overall_mape", {})[name] = score(allp)["mape"]
    return models, metrics


def save(models, metrics):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(models, ARTIFACTS / "model.joblib")
    (ARTIFACTS / "metrics.json").write_text(json.dumps(metrics, indent=2))


@lru_cache
def load_models():
    return joblib.load(ARTIFACTS / "model.joblib")


def load_metrics():
    return json.loads((ARTIFACTS / "metrics.json").read_text())


def history(conn, post_id, item_id):
    rows = conn.execute(
        "select date, qty, troop_strength, temp_c, activity_level from consumption_history"
        " where post_id = %s and item_id = %s order by date", (post_id, item_id)).fetchall()
    return pd.DataFrame(rows, columns=COLS).astype({c: float for c in COLS[1:]})


def forecast(conn, post_id, item_id, days):
    """Full forecast payload for one post × item, or None if unknown / no history."""
    hist = history(conn, post_id, item_id)
    meta = conn.execute(
        "select l.name, i.name, i.unit, s.quantity from locations l, items i"
        " left join stock_levels s on s.item_id = i.id and s.location_id = %s"
        " where l.id = %s and i.id = %s", (post_id, post_id, item_id)).fetchone()
    if hist.empty or meta is None or meta[3] is None:
        return None
    post_name, item_name, unit, stock = meta
    daily = forecast_series(load_models()[item_id], hist, days, seasonal_temp(hist))
    dos = days_of_supply(stock, daily)
    start = hist["date"].iloc[-1] + timedelta(days=1)
    return {
        "post_id": post_id, "item_id": item_id, "unit": unit, "stock": float(stock),
        "forecast": [{"date": (start + timedelta(days=i)).isoformat(), "qty": round(q, 2)} for i, q in enumerate(daily)],
        "days_of_supply": round(dos, 1),
        "explanation": explain(post_name, item_name, dos),
    }
