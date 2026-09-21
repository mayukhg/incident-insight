from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine.simulator import approve_policy, export_policy, simulate
from models import ApproveRequest, ApproveResponse, SimulateRequest, SimulateResponse
from routers.scenarios import require_scenario

router = APIRouter()


class ExportRequest(BaseModel):
    scenario_id: str
    proposal_id: str
    format: str = "json"


@router.post("/api/remediation/simulate", response_model=SimulateResponse)
def remediation_simulate(body: SimulateRequest) -> SimulateResponse:
    require_scenario(body.scenario_id)
    return simulate(body.scenario_id, body.rule, body.proposal_id, run_id="simulate")


@router.post("/api/remediation/approve", response_model=ApproveResponse)
def remediation_approve(body: ApproveRequest) -> ApproveResponse:
    require_scenario(body.scenario_id)
    digest = approve_policy(body.scenario_id, body.proposal_id, body.evidence_hash)
    return ApproveResponse(approved=True, evidence_hash=digest, proposal_id=body.proposal_id)


@router.post("/api/remediation/export", response_model=SimulateResponse)
def remediation_export(body: ExportRequest) -> SimulateResponse:
    require_scenario(body.scenario_id)
    if body.format not in {"json", "terraform"}:
        raise HTTPException(status_code=400, detail="Unsupported export format")
    return export_policy(body.scenario_id, body.proposal_id)
