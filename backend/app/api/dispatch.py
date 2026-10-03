from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_conn
from app.services import dispatch

router = APIRouter()


@router.get("/dispatch-plan")
def get_dispatch_plan():
    """FR-19: current recommendations, re-planned on every read so stock, route, weather and what-if changes
    always show (~0.1 s warm). Row ids survive re-plans while post × item × vehicle is unchanged."""
    with get_conn() as conn:
        dispatch.replan(conn)
        return {"target_days": dispatch.TARGET_DAYS, "plan": dispatch.plan(conn)}


class PlanStatus(BaseModel):
    status: Literal["approved", "dispatched"]


FROM = {"approved": ["proposed"], "dispatched": ["proposed", "approved"]}  # forward only


@router.patch("/dispatch-plan/{plan_id}")
def patch_dispatch_plan(plan_id: int, body: PlanStatus):
    """FR-20: officer approves / marks dispatched. Applies to the whole truck load (one truck = one trip), so a
    dispatched truck never leaves rows behind. The next read re-plans the rest around the commitment."""
    with get_conn() as conn:
        dispatch.lock(conn)
        cur = conn.execute("select status, vehicle_id from dispatch_plans where id = %s", (plan_id,)).fetchone()
        if cur is None:
            raise HTTPException(404, f"unknown plan row: {plan_id}")
        if cur[1] is None:
            raise HTTPException(409, "no vehicle assigned; nothing to dispatch")
        if cur[0] not in FROM[body.status]:
            raise HTTPException(409, f"cannot go from {cur[0]} to {body.status}")
        ids = [r[0] for r in conn.execute(
            "update dispatch_plans set status = %s where vehicle_id = %s and status = any(%s) returning id",
            (body.status, cur[1], FROM[body.status])).fetchall()]
    return {"id": plan_id, "status": body.status, "vehicle_id": cur[1], "updated": sorted(ids)}
