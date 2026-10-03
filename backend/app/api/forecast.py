from fastapi import APIRouter, HTTPException, Query

from app.db import get_conn
from app.services import forecasting

router = APIRouter()


@router.get("/forecast/metrics")
def metrics():
    try:
        return forecasting.load_metrics()
    except FileNotFoundError:
        raise HTTPException(503, "model not trained: run python backend/ml/train.py")


@router.get("/forecast/{post_id}/{item_id}")
def forecast(post_id: str, item_id: str, days: int = Query(14, ge=7, le=30)):
    try:
        with get_conn() as conn:
            out = forecasting.forecast(conn, post_id, item_id, days)
    except FileNotFoundError:
        raise HTTPException(503, "model not trained: run python backend/ml/train.py")
    if out is None:
        raise HTTPException(404, "unknown post/item")
    return out
