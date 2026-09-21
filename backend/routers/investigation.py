from __future__ import annotations

import json
import uuid
from threading import Lock

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from engine.planner import get_investigation, run_probe
from models import InvestigationResponse, NaturalLanguageRequest, ProbeRequest, ProbeResponse, RunAccepted
from routers.scenarios import require_scenario

router = APIRouter()

_RUNS: dict[str, InvestigationResponse] = {}
_LOCK = Lock()


def _run(scenario_id: str, *, force: bool = False, prompt: str | None = None) -> InvestigationResponse:
    require_scenario(scenario_id)
    run_id = uuid.uuid4().hex[:12]
    result = get_investigation(scenario_id, run_id=run_id, force=force, prompt=prompt)
    with _LOCK:
        _RUNS[result.run_id] = result
        _RUNS[f"latest:{scenario_id}"] = result
    return result


@router.post("/api/investigate/nl", response_model=InvestigationResponse)
def investigate_from_prompt(body: NaturalLanguageRequest) -> InvestigationResponse:
    return _run(body.scenario_id, force=True, prompt=body.prompt)


@router.get("/api/investigate/{scenario_id}", response_model=InvestigationResponse)
def investigate(scenario_id: str) -> InvestigationResponse:
    return _run(scenario_id)


@router.get("/api/investigate/{scenario_id}/stream")
async def investigate_stream(scenario_id: str):
    result = _run(scenario_id)

    async def events():
        for step in result.steps:
            yield {"event": "step", "data": json.dumps(step.model_dump())}
        yield {"event": "complete", "data": result.model_dump_json()}

    return EventSourceResponse(events())


@router.post("/api/investigate/{scenario_id}/runs", response_model=RunAccepted)
def start_run(scenario_id: str) -> RunAccepted:
    result = _run(scenario_id, force=True)
    return RunAccepted(run_id=result.run_id, status=result.run_status, scenario_id=scenario_id)


@router.get("/api/investigate/runs/{run_id}", response_model=InvestigationResponse)
def get_run(run_id: str) -> InvestigationResponse:
    with _LOCK:
        result = _RUNS.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown run")
    return result


@router.post("/api/probes", response_model=ProbeResponse)
def probe(body: ProbeRequest) -> ProbeResponse:
    require_scenario(body.scenario_id)
    try:
        node = run_probe(body.scenario_id, body.probe_id)
    except KeyError:
        raise HTTPException(status_code=400, detail="Probe is not allowlisted for this investigation")
    latest = _run(body.scenario_id)
    return ProbeResponse(run_id=latest.run_id, probe_id=body.probe_id, node=node)
