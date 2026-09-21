import type { InvestigationDto, ScenarioSummaryDto, SimulateDto, TelemetryDto } from "./schemas";
import type { CohortRow, EvidenceStatus, InvestigationNode, InvestigationSummary, Scenario, SimulationView } from "./types";

export function formatVolume(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value === 0) return "0 events";
  if (value >= 1_000_000) {
    const scaled = value / 1_000_000;
    return `${scaled >= 10 ? scaled.toFixed(1) : scaled.toFixed(2)}M`;
  }
  if (value >= 1000) {
    const scaled = value / 1000;
    return `${scaled >= 100 ? Math.round(scaled) : scaled.toFixed(0)}K`;
  }
  return value.toLocaleString("en-US");
}

export function formatRows(value: number): string {
  return `${formatVolume(value).replace(" events", "")} rows`;
}

export function formatPValue(value: number | null | undefined): string {
  if (value == null) return "n/a";
  if (value < 0.001) return "<0.001";
  return value.toFixed(3);
}

export function formatMoney(value: number): string {
  return `${new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value)}/hr`;
}

export function formatWindow(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const day = start.toLocaleString("en-GB", { day: "2-digit", month: "short", timeZone: "UTC" });
  const from = start.toLocaleString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
  const to = end.toLocaleString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
  return `${day} · ${from}–${to} UTC`;
}

export function formatClock(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
}

function mapStatus(stepStatus: string, stepNumber: number): EvidenceStatus {
  if (stepStatus === "INCONCLUSIVE") return "inconclusive";
  if (stepStatus === "CORRELATED" || stepNumber === 1) return "success";
  if (stepStatus === "ANOMALY_DETECTED") return "anomaly";
  return "success";
}

function mapCohorts(rows: InvestigationDto["steps"][number]["variance_summary"]): CohortRow[] {
  return rows.map((row) => ({
    slice: row.slice,
    baselineVolume: formatVolume(row.baseline_vol),
    baselineAuth: row.baseline_auth_pct ?? 0,
    incidentVolume: formatVolume(row.incident_vol),
    incidentAuth: row.incident_auth_pct ?? 0,
    delta: row.delta_pct ?? 0,
    pValue: formatPValue(row.p_value),
  }));
}

function mapNode(step: InvestigationDto["steps"][number], stale: boolean): InvestigationNode {
  return {
    id: step.step_id,
    step: String(step.step_number).padStart(2, "0"),
    title: step.title,
    finding: step.finding,
    runtime: `${step.execution_time_ms}ms`,
    rows: formatRows(step.rows_scanned),
    status: mapStatus(step.status, step.step_number),
    sql: step.executed_sql.replace(/ \?/g, " ?").replace(/;?$/, ";"),
    cohorts: mapCohorts(step.variance_summary),
    chartLabel: step.chart_label,
    stale,
  };
}

export function mapSummary(dto: ScenarioSummaryDto): InvestigationSummary {
  return {
    id: dto.id,
    name: dto.name,
    shortName: dto.short_name,
    status: dto.status === "MIXED_EVIDENCE" ? "mixed" : "definitive",
  };
}

export function mapInvestigation(detail: InvestigationDto, telemetry: TelemetryDto, summary?: ScenarioSummaryDto): Scenario {
  const mixed = detail.status === "MIXED_EVIDENCE";
  const rca = detail.root_cause_analysis;
  const stale = detail.verification.stale;
  const marker = telemetry.milestones[0];
  const scenario: Scenario = {
    id: detail.scenario_id,
    shortName: summary?.short_name ?? detail.scenario_id,
    title: summary?.name ?? rca.title,
    status: mixed ? "mixed" : "definitive",
    baselineAuth: detail.kpis.baseline_auth_pct,
    incidentAuth: detail.kpis.incident_auth_pct,
    delta: detail.kpis.delta_pct,
    gtvRisk: formatMoney(detail.kpis.gtv_at_risk_hourly),
    window: summary?.anomaly_window[0] && summary.anomaly_window[1] ? formatWindow(summary.anomaly_window[0], summary.anomaly_window[1]) : "",
    nodes: detail.steps.map((step) => mapNode(step, stale)),
    chart: telemetry.buckets.map((bucket) => ({
      time: formatClock(bucket.timestamp),
      baseline: bucket.baseline_auth_rate,
      incident: bucket.auth_rate,
      latency: bucket.p95_latency_ms,
    })),
    rootCause: rca.title,
    summary: rca.culprit_trigger,
    confidence: Math.round(rca.confidence_score * 100),
    lostTransactions: `${rca.impact.impacted_transactions.toLocaleString("en-US")} txns`,
    customerAbandonment: `+${Math.round(rca.impact.repeat_checkout_drop_pct)}%`,
    evidenceVerified: detail.verification.complete && detail.verification.all_queries_executed && !detail.verification.failed && !stale,
    stale,
    markerTime: marker ? formatClock(marker.timestamp) : "14:05",
    markerLabel: marker?.label ?? (mixed ? "Observed shift" : "Deploy #4481"),
    runId: detail.run_id,
    runStatus: detail.run_status,
  };
  if (!mixed && rca.default_rule) {
    scenario.targetRule = rca.default_rule.target_rule;
    scenario.proposalId = rca.default_rule.proposal_id;
  }
  if (mixed) {
    scenario.counterEvidence = rca.counter_evidence ?? [];
    scenario.probes = (rca.probes ?? []).map((probe) => ({
      probeId: probe.probe_id,
      title: probe.title,
      description: probe.description,
      sql: probe.sql,
    }));
  }
  return scenario;
}

export function mapSimulation(dto: SimulateDto): SimulationView {
  return {
    projectedAuth: dto.projected_global_auth_rate,
    recoveredGtv: formatMoney(dto.recovered_revenue_hourly),
    json: JSON.stringify(dto.policy_export.json_rule, null, 2),
    terraform: dto.policy_export.terraform_diff,
    evidenceHash: dto.policy_export.evidence_hash,
    proposalId: dto.proposal_id,
  };
}
