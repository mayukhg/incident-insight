from __future__ import annotations

from fastapi import APIRouter

from engine.telemetry import load_telemetry
from models import TelemetryResponse
from routers.scenarios import require_scenario

router = APIRouter()


@router.get("/api/telemetry/{scenario_id}", response_model=TelemetryResponse)
def telemetry(scenario_id: str) -> TelemetryResponse:
    require_scenario(scenario_id)
    return load_telemetry(scenario_id)
