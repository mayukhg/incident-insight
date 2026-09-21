from __future__ import annotations

from fastapi import APIRouter, HTTPException

from engine.planner import compute_kpis
from models import ScenarioSummary
from seed_data import SCENARIOS, iso_z

router = APIRouter()


@router.get("/api/scenarios", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    summaries: list[ScenarioSummary] = []
    for spec in SCENARIOS.values():
        kpis = compute_kpis(spec)
        summaries.append(
            ScenarioSummary(
                id=spec.id,
                name=spec.name,
                short_name=spec.short_name,
                status=spec.status,
                baseline_window=[iso_z(spec.baseline_start), iso_z(spec.baseline_end)],
                anomaly_window=[iso_z(spec.anomaly_start), iso_z(spec.anomaly_end)],
                kpis=kpis,
            )
        )
    return summaries


def require_scenario(scenario_id: str):
    spec = SCENARIOS.get(scenario_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown investigation")
    return spec
