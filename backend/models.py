from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScenarioKpis(BaseModel):
    baseline_auth_pct: float
    incident_auth_pct: float
    delta_pct: float
    gtv_at_risk_hourly: float


class ScenarioSummary(BaseModel):
    id: str
    name: str
    short_name: str
    status: str
    baseline_window: list[str]
    anomaly_window: list[str]
    kpis: ScenarioKpis


class VarianceRow(BaseModel):
    slice: str
    baseline_vol: int | None = None
    baseline_auth_pct: float | None = None
    incident_vol: int | None = None
    incident_auth_pct: float | None = None
    delta_pct: float | None = None
    p_value: float | None = None
    is_anomalous: bool = False


class InvestigationStep(BaseModel):
    step_id: str
    step_number: int
    title: str
    status: str
    finding: str
    chart_label: str
    execution_time_ms: int
    rows_scanned: int
    executed_sql: str
    variance_summary: list[VarianceRow]
    run_state: str = "completed"


class ImpactMetrics(BaseModel):
    revenue_lost_hourly: float
    impacted_transactions: int
    repeat_checkout_drop_pct: float


class Probe(BaseModel):
    probe_id: str
    title: str
    description: str
    sql: str


class DefaultRule(BaseModel):
    proposal_id: str
    source_gateway: str
    target_gateway: str
    filter_country: str | None = None
    filter_card_type: str | None = None
    filter_card_brand: str | None = None
    target_rule: str


class RootCauseAnalysis(BaseModel):
    title: str
    culprit_trigger: str
    confidence_score: float
    impact: ImpactMetrics
    counter_evidence: list[str] = Field(default_factory=list)
    probes: list[Probe] = Field(default_factory=list)
    default_rule: DefaultRule | None = None


class VerificationState(BaseModel):
    complete: bool
    stale: bool
    all_queries_executed: bool
    failed: bool = False


class InvestigationResponse(BaseModel):
    scenario_id: str
    status: str
    run_id: str
    run_status: str
    kpis: ScenarioKpis
    steps: list[InvestigationStep]
    root_cause_analysis: RootCauseAnalysis
    verification: VerificationState
    planner_source: str = "template"
    replan_count: int = 0


class TelemetryBucket(BaseModel):
    timestamp: str
    auth_rate: float
    baseline_auth_rate: float
    p95_latency_ms: float
    volume: int


class TelemetryMilestone(BaseModel):
    timestamp: str
    type: str
    label: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TelemetryResponse(BaseModel):
    buckets: list[TelemetryBucket]
    milestones: list[TelemetryMilestone]


class RemediationRule(BaseModel):
    source_gateway: str
    target_gateway: str
    filter_country: str | None = None
    filter_card_type: str | None = None
    filter_card_brand: str | None = None


class SimulateRequest(BaseModel):
    scenario_id: str
    proposal_id: str | None = None
    rule: RemediationRule | None = None


class PolicyExport(BaseModel):
    json_rule: dict[str, Any]
    terraform_diff: str
    evidence_hash: str
    filename_json: str = "routing-policy.json"
    filename_tf: str = "routing-policy.tf"


class SimulateResponse(BaseModel):
    projected_global_auth_rate: float
    projected_lift_pct: float
    recovered_revenue_hourly: float
    recovered_txns_hourly: int
    policy_export: PolicyExport
    proposal_id: str


class RunAccepted(BaseModel):
    run_id: str
    status: str
    scenario_id: str


class ProbeRequest(BaseModel):
    scenario_id: str
    probe_id: str


class NaturalLanguageRequest(BaseModel):
    scenario_id: str
    prompt: str = Field(min_length=8, max_length=2000)


class ApproveRequest(BaseModel):
    scenario_id: str
    proposal_id: str
    evidence_hash: str


class ApproveResponse(BaseModel):
    approved: bool
    evidence_hash: str
    proposal_id: str


class ProbeResponse(BaseModel):
    run_id: str
    probe_id: str
    node: InvestigationStep
