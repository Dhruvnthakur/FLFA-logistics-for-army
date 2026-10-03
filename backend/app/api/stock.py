from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, Field, field_validator

from app.db import get_conn
from app.services import stock

router = APIRouter()

MAX_CLOCK_SKEW = timedelta(minutes=5)
MAX_AGE = timedelta(days=7)


class Reading(BaseModel):
    location_id: str = Field(min_length=1, max_length=16)
    item_id: str = Field(min_length=1, max_length=32)
    quantity: float = Field(ge=0, allow_inf_nan=False)
    timestamp: AwareDatetime  # naive timestamps are ambiguous → rejected

    @field_validator("timestamp")
    @classmethod
    def sane_timestamp(cls, ts):
        now = datetime.now(timezone.utc)
        if ts > now + MAX_CLOCK_SKEW:
            raise ValueError("timestamp is in the future")
        if ts < now - MAX_AGE:
            raise ValueError(f"timestamp older than {MAX_AGE.days} days")
        return ts


@router.post("/readings")
def post_readings(body: Reading | list[Reading]):
    """FR-6: one reading or a batch (the simulator sends a batch per tick). All-or-nothing."""
    readings = body if isinstance(body, list) else [body]
    if not 1 <= len(readings) <= 500:
        raise HTTPException(422, "send 1..500 readings")
    out = []
    with get_conn() as conn:  # one transaction: any unknown pair rolls back the whole batch
        leads = stock.lead_times(conn)
        for r in readings:
            # stale readings are logged but never overwrite a newer level
            row = conn.execute(
                "update stock_levels set quantity = %s, updated_at = %s"
                " where location_id = %s and item_id = %s and updated_at <= %s returning 1",
                (r.quantity, r.timestamp, r.location_id, r.item_id, r.timestamp)).fetchone()
            s = stock.one_stock(conn, r.location_id, r.item_id, leads)
            if s is None:
                raise HTTPException(422, f"unknown location/item: {r.location_id}/{r.item_id}")
            conn.execute("insert into stock_readings (location_id, item_id, quantity, ts) values (%s, %s, %s, %s)",
                         (r.location_id, r.item_id, r.quantity, r.timestamp))
            stock.sync_alert(conn, s)
            out.append({"location_id": r.location_id, "item_id": r.item_id, "applied": row is not None,
                        "status": s["status"], "days_of_supply": s["days_of_supply"]})
    return {"accepted": len(out), "results": out}


@router.get("/stock")
def get_stock():
    with get_conn() as conn:
        return {"thresholds": stock.thresholds(), "stock": stock.all_stock(conn)}


@router.get("/alerts")
def get_alerts():
    with get_conn() as conn:
        return {"alerts": stock.open_alerts(conn)}
