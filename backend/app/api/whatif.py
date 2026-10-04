from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import get_conn
from app.services import whatif

router = APIRouter()


class CloseRoute(BaseModel):
    type: Literal["close_route"]
    route_id: str = Field(min_length=1, max_length=16)
    status: Literal["open", "degraded", "closed"] = "closed"


class Storm(BaseModel):
    type: Literal["storm"]
    route_id: str = Field(min_length=1, max_length=16)
    radius_km: float = Field(default=15, ge=5, le=100, allow_inf_nan=False)


class TroopChange(BaseModel):
    type: Literal["troop_change"]
    post_id: str = Field(min_length=1, max_length=16)
    strength: int = Field(ge=1, le=1000)


Scenario = Annotated[CloseRoute | Storm | TroopChange, Field(discriminator="type")]


@router.get("/whatif")
def get_whatif():
    """Scenarios currently applied on top of the baseline (empty = baseline)."""
    with get_conn() as conn:
        return {"active": whatif.active(conn)}


@router.post("/whatif")
def post_whatif(body: Scenario):
    """FR-23/24: apply one scenario, re-plan, return the before/after diff. Stacks until /whatif/reset."""
    try:
        with get_conn() as conn:
            return whatif.apply(conn, body.model_dump())
    except LookupError as e:
        raise HTTPException(404, str(e))
    except whatif.TooMany as e:
        raise HTTPException(409, str(e))


@router.post("/whatif/reset")
def post_reset():
    with get_conn() as conn:
        return whatif.reset(conn)
