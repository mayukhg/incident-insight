from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException

from engine.planner import compute_kpis, get_investigation
from engine.query_gate import execute
from engine.stats import auth_rate
from engine.taxonomy import CONFIDENCE_GATE
from models import PolicyExport, RemediationRule, SimulateResponse
from seed_data import SCENARIOS


_last_simulation: dict[str, SimulateResponse] = {}
_approved_hashes: set[str] = set()


def simulate(scenario_id: str, rule: RemediationRule | None, proposal_id: str | None, *, run_id: str) -> SimulateResponse:
    spec = SCENARIOS.get(scenario_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown investigation")
    investigation = get_investigation(scenario_id, run_id=run_id)
    if investigation.status != "DEFINITIVE_RCA":
        raise HTTPException(status_code=409, detail="Simulation rejected: mixed or incomplete evidence")
    if investigation.root_cause_analysis.confidence_score < CONFIDENCE_GATE:
        raise HTTPException(status_code=409, detail="Simulation rejected: confidence below 80%")
    if not investigation.verification.all_queries_executed or investigation.verification.failed:
        raise HTTPException(status_code=409, detail="Simulation rejected: evidence is incomplete")

    resolved = rule
    if resolved is None:
        default = investigation.root_cause_analysis.default_rule
        if default is None:
            raise HTTPException(status_code=409, detail="No verified remediation proposal")
        resolved = RemediationRule(
            source_gateway=default.source_gateway,
            target_gateway=default.target_gateway,
            filter_country=default.filter_country,
            filter_card_type=default.filter_card_type,
            filter_card_brand=default.filter_card_brand,
        )
        proposal_id = default.proposal_id
    proposal_id = proposal_id or (
        investigation.root_cause_analysis.default_rule.proposal_id
        if investigation.root_cause_analysis.default_rule
        else "default"
    )

    source_where = "gateway_id = ? AND timestamp >= ? AND timestamp < ?"
    source_params: list[object] = [resolved.source_gateway, spec.anomaly_start, spec.anomaly_end]
    target_where = "gateway_id = ? AND timestamp >= ? AND timestamp < ?"
    target_params: list[object] = [resolved.target_gateway, spec.anomaly_start, spec.anomaly_end]
    if resolved.filter_country:
        source_where += " AND bin_country = ?"
        source_params.append(resolved.filter_country)
    if resolved.filter_card_type:
        source_where += " AND card_type = ?"
        source_params.append(resolved.filter_card_type)
    if resolved.filter_card_brand:
        source_where += " AND card_brand = ?"
        source_params.append(resolved.filter_card_brand)

    source = execute(
        f"SELECT COUNT(*) AS volume, COUNT(*) FILTER (WHERE status='authorized') AS authorized, COALESCE(SUM(amount),0) AS gtv FROM transactions WHERE {source_where}",
        source_params,
    )
    target = execute(
        f"SELECT COUNT(*) AS volume, COUNT(*) FILTER (WHERE status='authorized') AS authorized FROM transactions WHERE {target_where}",
        target_params,
    )
    kpis = compute_kpis(spec)
    src_n, src_auth, src_gtv = source.rows[0]
    tgt_n, tgt_auth = target.rows[0]
    src_n, src_auth, tgt_n, tgt_auth = int(src_n), int(src_auth), int(tgt_n), int(tgt_auth)
    src_rate = auth_rate(src_auth, src_n)
    tgt_rate = auth_rate(tgt_auth, tgt_n)
    hours = 2.0
    lift_pp = max(0.0, tgt_rate - src_rate)
    recovered_txns = int(round((lift_pp / 100.0) * src_n / hours))
    avg_ticket = float(src_gtv) / src_n if src_n else 0.0
    recovered_gtv = round(recovered_txns * avg_ticket, 2)
    shifted_auth = src_n * (tgt_rate / 100.0)
    global_n_base = None
    global_stats = execute(
        "SELECT COUNT(*) AS volume, COUNT(*) FILTER (WHERE status='authorized') AS authorized FROM transactions WHERE timestamp >= ? AND timestamp < ?",
        [spec.anomaly_start, spec.anomaly_end],
    )
    glob_n, glob_auth = int(global_stats.rows[0][0]), int(global_stats.rows[0][1])
    projected_auth = 0.0
    if glob_n:
        projected_auth = round(100.0 * (glob_auth - src_auth + shifted_auth) / glob_n, 1)
    lift_vs_incident = round(projected_auth - kpis.incident_auth_pct, 1)

    json_rule = {
        "rule_id": f"dyn_failover_{proposal_id}",
        "priority": 1,
        "action": "ROUTE_OVERRIDE",
        "conditions": {
            "bin_country": resolved.filter_country,
            "card_type": resolved.filter_card_type,
            "card_brand": resolved.filter_card_brand,
            "original_gateway": resolved.source_gateway,
        },
        "destination_gateway": resolved.target_gateway,
        "ttl_seconds": 3600,
    }
    terraform = (
        f'resource "payment_router_override" "{resolved.source_gateway}_{proposal_id}" {{\n'
        f'  name        = "{resolved.source_gateway} to {resolved.target_gateway}"\n'
        f"  priority    = 1\n"
        f'  destination = "{resolved.target_gateway}"\n'
        f'  conditions  = "gateway == \'{resolved.source_gateway}\'"\n'
        f'  status      = "active"\n'
        f"}}"
    )
    evidence = {
        "scenario_id": scenario_id,
        "proposal_id": proposal_id,
        "sql": [source.sql, target.sql],
        "steps": [step.executed_sql for step in investigation.steps],
        "confidence": investigation.root_cause_analysis.confidence_score,
        "windows": [spec.baseline_start, spec.baseline_end, spec.anomaly_start, spec.anomaly_end],
        "planner_source": investigation.planner_source,
        "replan_count": investigation.replan_count,
    }
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()
    response = SimulateResponse(
        projected_global_auth_rate=projected_auth,
        projected_lift_pct=lift_vs_incident,
        recovered_revenue_hourly=recovered_gtv,
        recovered_txns_hourly=recovered_txns,
        proposal_id=proposal_id,
        policy_export=PolicyExport(
            json_rule=json_rule,
            terraform_diff=terraform,
            evidence_hash=digest,
        ),
    )
    _last_simulation[f"{scenario_id}:{proposal_id}"] = response
    return response


def approve_policy(scenario_id: str, proposal_id: str, evidence_hash: str) -> str:
    key = f"{scenario_id}:{proposal_id}"
    cached = _last_simulation.get(key)
    if cached is None or cached.policy_export.evidence_hash != evidence_hash:
        raise HTTPException(status_code=409, detail="Approve rejected: evidence hash mismatch")
    _approved_hashes.add(evidence_hash)
    return evidence_hash


def export_policy(scenario_id: str, proposal_id: str) -> SimulateResponse:
    key = f"{scenario_id}:{proposal_id}"
    cached = _last_simulation.get(key)
    if cached is None:
        cached = simulate(scenario_id, None, proposal_id, run_id="export")
    if cached.policy_export.evidence_hash not in _approved_hashes:
        raise HTTPException(status_code=409, detail="Export rejected: engineer approval required")
    return cached
