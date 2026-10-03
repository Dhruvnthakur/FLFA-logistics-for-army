"""Train per-item demand models from consumption_history and write backend/ml/artifacts/.

Run from repo root (backend venv active): python backend/ml/train.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import get_conn  # noqa: E402
from app.services import forecasting as f  # noqa: E402

if __name__ == "__main__":
    with get_conn() as conn:
        rows = conn.execute(
            "select post_id, item_id, date, qty, troop_strength, temp_c, activity_level from consumption_history"
        ).fetchall()
    df = pd.DataFrame(rows, columns=["post_id", "item_id"] + f.COLS).astype({c: float for c in f.COLS[1:]})
    models, metrics = f.train(df)
    f.save(models, metrics)
    for item, m in metrics["per_item"].items():
        print(f"{item:16s} model MAPE {m['model']['mape']:6.2f}%  baseline {m['baseline']['mape']:6.2f}%")
    print("overall MAPE", metrics["overall_mape"])
