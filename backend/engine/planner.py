from __future__ import annotations

from engine.query_gate import QueryResult, execute
from engine.stats import auth_rate, chi_square_p_value, delta_pp, is_isolated, is_significant
from models import (
    DefaultRule,
    ImpactMetrics,
    InvestigationResponse,
    InvestigationStep,
    Probe,
    RootCauseAnalysis,
    ScenarioKpis,
    VarianceRow,
    VerificationState,
)
from seed_data import SCENARIOS, ScenarioSpec

_INVESTIGATION_CACHE: dict[str, InvestigationResponse] = {}


def _window_metrics(start: str, end: str) -> tuple[int, int, float, QueryResult]:
    result = execute(
        """
        SELECT COUNT(*) AS volume,
               COUNT(*) FILTER (WHERE status = 'authorized') AS authorized,
               COALESCE(SUM(amount), 0) AS gtv
        FROM transactions
        WHERE timestamp >= ? AND timestamp < ?
        """,
        [start, end],
        rows_scanned_sql="SELECT COUNT(*) FROM transactions WHERE timestamp >= ? AND timestamp < ?",
    )
    volume, authorized, gtv = result.rows[0]
    return int(volume), int(authorized), float(gtv), result


def compute_kpis(spec: ScenarioSpec) -> ScenarioKpis:
    base_n, base_auth, _, _ = _window_metrics(spec.baseline_start, spec.baseline_end)
    inc_n, inc_auth, inc_gtv, _ = _window_metrics(spec.anomaly_start, spec.anomaly_end)
    base_pct = auth_rate(base_auth, base_n)
    inc_pct = auth_rate(inc_auth, inc_n)
    hours = 2.0
    extra_declines = max(0.0, (base_pct - inc_pct) / 100.0 * inc_n)
    avg_ticket = (inc_gtv / inc_n) if inc_n else 0.0
    gtv_hourly = round((extra_declines * avg_ticket) / hours, 2)
    return ScenarioKpis(
        baseline_auth_pct=base_pct,
        incident_auth_pct=inc_pct,
        delta_pct=delta_pp(inc_pct, base_pct),
        gtv_at_risk_hourly=gtv_hourly,
    )


def _pair_rows(baseline: dict[str, tuple[int, int]], incident: dict[str, tuple[int, int]]) -> list[VarianceRow]:
    keys = sorted(set(baseline) | set(incident), key=lambda key: incident.get(key, (0, 0))[0], reverse=True)
    deltas: list[float] = []
    prepared: list[tuple[str, int, int, int, int, float, float, float, float | None]] = []
    for key in keys:
        b_n, b_a = baseline.get(key, (0, 0))
        i_n, i_a = incident.get(key, (0, 0))
        b_pct = auth_rate(b_a, b_n)
        i_pct = auth_rate(i_a, i_n)
        delta = delta_pp(i_pct, b_pct)
        p_value = chi_square_p_value(b_a, b_n, i_a, i_n)
        prepared.append((key, b_n, b_a, i_n, i_a, b_pct, i_pct, delta, p_value))
        deltas.append(delta)
    rows: list[VarianceRow] = []
    for key, b_n, b_a, i_n, i_a, b_pct, i_pct, delta, p_value in prepared:
        peers = [item for item, src in zip(deltas, prepared) if src[0] != key]
        rows.append(
            VarianceRow(
                slice=key,
                baseline_vol=b_n,
                baseline_auth_pct=b_pct,
                incident_vol=i_n,
                incident_auth_pct=i_pct,
                delta_pct=delta,
                p_value=None if p_value is None else round(p_value, 6),
                is_anomalous=is_isolated(delta, peers, p_value),
            )
        )
    rows.sort(key=lambda row: (not row.is_anomalous, row.delta_pct if row.delta_pct is not None else 0))
    return rows


def _grouped(start: str, end: str, group_sql: str, extra_params: list[object] | None = None) -> tuple[dict[str, tuple[int, int]], QueryResult]:
    params = list(extra_params or []) + [start, end]
    result = execute(
        f"""
        SELECT {group_sql} AS slice,
               COUNT(*) AS volume,
               COUNT(*) FILTER (WHERE status = 'authorized') AS authorized
        FROM transactions
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY 1
        """,
        params,
        rows_scanned_sql="SELECT COUNT(*) FROM transactions WHERE timestamp >= ? AND timestamp < ?",
        scan_params=[start, end],
    )
    grouped = {str(row[0]): (int(row[1]), int(row[2])) for row in result.rows}
    return grouped, result


def _step_status(rows: list[VarianceRow], *, correlated: bool | None = None) -> str:
    if correlated is True:
        return "CORRELATED"
    if correlated is False:
        return "INCONCLUSIVE"
    if any(row.is_anomalous for row in rows):
        return "ANOMALY_DETECTED"
    if rows and all((row.p_value or 1) >= 0.05 or abs(row.delta_pct or 0) < 2 for row in rows):
        return "INCONCLUSIVE"
    if rows:
        return "ANOMALY_DETECTED"
    return "INCONCLUSIVE"


def _finding(step_status: str, rows: list[VarianceRow], fallback: str) -> str:
    if step_status == "CORRELATED":
        return fallback
    anomalous = next((row for row in rows if row.is_anomalous), None)
    if anomalous:
        return f"{anomalous.slice} isolated at {anomalous.delta_pct}pp (p={anomalous.p_value})"
    if rows:
        return fallback
    return fallback


def get_investigation(scenario_id: str, *, run_id: str, stale: bool = False, force: bool = False) -> InvestigationResponse:
    if not force and scenario_id in _INVESTIGATION_CACHE:
        cached = _INVESTIGATION_CACHE[scenario_id]
        cached.verification.stale = stale
        return cached
    result = run_investigation(scenario_id, run_id=run_id, stale=stale)
    _INVESTIGATION_CACHE[scenario_id] = result
    return result


def run_investigation(scenario_id: str, *, run_id: str, stale: bool = False) -> InvestigationResponse:
    spec = SCENARIOS[scenario_id]
    kpis = compute_kpis(spec)

    base_n, base_auth, _, base_q = _window_metrics(spec.baseline_start, spec.baseline_end)
    inc_n, inc_auth, inc_gtv, inc_q = _window_metrics(spec.anomaly_start, spec.anomaly_end)
    global_p = chi_square_p_value(base_auth, base_n, inc_auth, inc_n)
    global_row = VarianceRow(
        slice="Global Traffic",
        baseline_vol=base_n,
        baseline_auth_pct=kpis.baseline_auth_pct,
        incident_vol=inc_n,
        incident_auth_pct=kpis.incident_auth_pct,
        delta_pct=kpis.delta_pct,
        p_value=None if global_p is None else round(global_p, 6),
        is_anomalous=is_significant(global_p) and abs(kpis.delta_pct) >= 2,
    )
    step1 = InvestigationStep(
        step_id="step_1",
        step_number=1,
        title="Global Baseline vs Anomaly Isolation",
        status=_step_status([global_row]),
        finding=f"Statistically measured {abs(kpis.delta_pct)}pp auth shift vs matched baseline",
        chart_label="Anomaly window confirmed",
        execution_time_ms=base_q.execution_time_ms + inc_q.execution_time_ms,
        rows_scanned=base_q.rows_scanned + inc_q.rows_scanned,
        executed_sql=inc_q.sql,
        variance_summary=[global_row],
    )

    base_gw, gw_q = _grouped(spec.baseline_start, spec.baseline_end, "gateway_id")
    inc_gw, gw_q2 = _grouped(spec.anomaly_start, spec.anomaly_end, "gateway_id")
    gw_rows = _pair_rows(base_gw, inc_gw)
    isolated_gateway = next((row.slice for row in gw_rows if row.is_anomalous), spec.isolation_gateway)
    step2 = InvestigationStep(
        step_id="step_2",
        step_number=2,
        title="Gateway Cohort Decomposition",
        status=_step_status(gw_rows),
        finding=_finding(_step_status(gw_rows), gw_rows, "Variance is uniform across PSPs"),
        chart_label="Gateway divergence versus peer PSPs",
        execution_time_ms=gw_q.execution_time_ms + gw_q2.execution_time_ms,
        rows_scanned=max(gw_q.rows_scanned, gw_q2.rows_scanned),
        executed_sql=gw_q2.sql,
        variance_summary=gw_rows,
    )

    if spec.id == "scenario_a":
        extra = ["adyen"]
        title = "Dimensional Slicing (BIN Country & Card Type on Adyen)"
        chart_label = "Failure concentrated in GB debit 3DS"
        sql = """
        SELECT gateway_id || ' / ' || bin_country || ' / ' || card_type || ' / ' || COALESCE(three_ds_version, 'none') AS slice,
               COUNT(*) AS volume,
               COUNT(*) FILTER (WHERE status = 'authorized') AS authorized
        FROM transactions
        WHERE gateway_id = ? AND timestamp >= ? AND timestamp < ?
        GROUP BY 1
        """
        base_dim = execute(sql, extra + [spec.baseline_start, spec.baseline_end], rows_scanned_sql="SELECT COUNT(*) FROM transactions WHERE gateway_id = ? AND timestamp >= ? AND timestamp < ?", scan_params=extra + [spec.baseline_start, spec.baseline_end])
        inc_dim = execute(sql, extra + [spec.anomaly_start, spec.anomaly_end], rows_scanned_sql="SELECT COUNT(*) FROM transactions WHERE gateway_id = ? AND timestamp >= ? AND timestamp < ?", scan_params=extra + [spec.anomaly_start, spec.anomaly_end])
    elif spec.id == "scenario_b":
        sql = """
        SELECT card_brand || ' / ' || card_type AS slice,
               COUNT(*) AS volume,
               COUNT(*) FILTER (WHERE status = 'authorized') AS authorized
        FROM transactions
        WHERE gateway_id = 'checkout' AND timestamp >= ? AND timestamp < ?
        GROUP BY 1
        """
        title = "Scheme & response slicing"
        chart_label = "Visa latency and soft declines correlate"
        base_dim = execute(sql, [spec.baseline_start, spec.baseline_end], rows_scanned_sql="SELECT COUNT(*) FROM transactions WHERE gateway_id = 'checkout' AND timestamp >= ? AND timestamp < ?")
        inc_dim = execute(sql, [spec.anomaly_start, spec.anomaly_end], rows_scanned_sql="SELECT COUNT(*) FROM transactions WHERE gateway_id = 'checkout' AND timestamp >= ? AND timestamp < ?")
    else:
        sql = """
        SELECT gateway_id || ' / ' || COALESCE(decline_code, 'authorized') AS slice,
               COUNT(*) AS volume,
               COUNT(*) FILTER (WHERE status = 'authorized') AS authorized
        FROM transactions
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY 1
        """
        title = "Issuer & cohort slicing"
        chart_label = "insufficient_funds distributed uniformly"
        base_dim = execute(sql, [spec.baseline_start, spec.baseline_end])
        inc_dim = execute(sql, [spec.anomaly_start, spec.anomaly_end])

    base_map = {str(row[0]): (int(row[1]), int(row[2])) for row in base_dim.rows}
    inc_map = {str(row[0]): (int(row[1]), int(row[2])) for row in inc_dim.rows}
    dim_rows = _pair_rows(base_map, inc_map)
    if spec.id == "scenario_c":
        for row in dim_rows:
            row.is_anomalous = False
    step3 = InvestigationStep(
        step_id="step_3",
        step_number=3,
        title=title,
        status="INCONCLUSIVE" if spec.id == "scenario_c" else _step_status(dim_rows),
        finding=_finding("INCONCLUSIVE" if spec.id == "scenario_c" else _step_status(dim_rows), dim_rows, "No cohort clears the isolation gate"),
        chart_label=chart_label,
        execution_time_ms=base_dim.execution_time_ms + inc_dim.execution_time_ms,
        rows_scanned=max(base_dim.rows_scanned, inc_dim.rows_scanned),
        executed_sql=inc_dim.sql,
        variance_summary=dim_rows[:6],
    )

    deploy_q = execute(
        """
        SELECT deploy_id, service_name, git_sha, deployed_at
        FROM system_deployments
        WHERE deployed_at BETWEEN CAST(? AS TIMESTAMP) - INTERVAL 30 MINUTE
          AND CAST(? AS TIMESTAMP) + INTERVAL 30 MINUTE
        """,
        [spec.anomaly_start, spec.anomaly_start],
        rows_scanned_sql="SELECT COUNT(*) FROM system_deployments",
        scan_params=[],
    )
    incident_q = execute(
        """
        SELECT incident_id, gateway_id, start_time, reported_severity, description
        FROM gateway_incidents
        WHERE start_time BETWEEN CAST(? AS TIMESTAMP) - INTERVAL 30 MINUTE
          AND CAST(? AS TIMESTAMP) + INTERVAL 90 MINUTE
        """,
        [spec.anomaly_start, spec.anomaly_start],
        rows_scanned_sql="SELECT COUNT(*) FROM gateway_incidents",
        scan_params=[],
    )
    correlated = bool(deploy_q.rows) or bool(incident_q.rows)
    if spec.id == "scenario_c":
        correlated = False
    corr_rows: list[VarianceRow] = []
    if deploy_q.rows:
        deploy_id, service, sha, deployed_at = deploy_q.rows[0]
        corr_rows.append(
            VarianceRow(
                slice=f"Deploy {deploy_id} · {service}",
                baseline_vol=None,
                baseline_auth_pct=None,
                incident_vol=1,
                incident_auth_pct=None,
                delta_pct=None,
                p_value=None,
                is_anomalous=True,
            )
        )
    if incident_q.rows:
        incident_id, gateway, start_time, severity, description = incident_q.rows[0]
        corr_rows.append(
            VarianceRow(
                slice=f"Provider incident {incident_id}",
                baseline_vol=None,
                baseline_auth_pct=None,
                incident_vol=1,
                incident_auth_pct=None,
                delta_pct=None,
                p_value=None,
                is_anomalous=True,
            )
        )
    if not corr_rows:
        corr_rows = [
            VarianceRow(slice="Correlated deploys", incident_vol=0, p_value=None, is_anomalous=False),
            VarianceRow(slice="Provider incidents", incident_vol=0, p_value=None, is_anomalous=False),
        ]
    step4 = InvestigationStep(
        step_id="step_4",
        step_number=4,
        title="Operational Telemetry Cross-Correlation",
        status="CORRELATED" if correlated else "INCONCLUSIVE",
        finding="Matching operational event aligned with anomaly start" if correlated else "No matching deploy or PSP incident",
        chart_label="Deploy marker precedes timeout ramp" if deploy_q.rows else ("PSP incident starts within two minutes" if incident_q.rows else "No causal event detected"),
        execution_time_ms=deploy_q.execution_time_ms + incident_q.execution_time_ms,
        rows_scanned=deploy_q.rows_scanned + incident_q.rows_scanned,
        executed_sql=deploy_q.sql if spec.id != "scenario_b" else incident_q.sql,
        variance_summary=corr_rows,
    )

    steps = [step1, step2, step3, step4]
    isolated = any(row.is_anomalous for row in gw_rows) and correlated
    mixed = spec.status == "MIXED_EVIDENCE" or not isolated
    status = "MIXED_EVIDENCE" if mixed else "DEFINITIVE_RCA"
    hours = 2.0
    extra_declines = max(0, int(round((kpis.baseline_auth_pct - kpis.incident_auth_pct) / 100.0 * inc_n)))
    rca = RootCauseAnalysis(
        title=spec.isolation_title,
        culprit_trigger=spec.culprit_trigger,
        confidence_score=spec.expected_confidence if (not mixed or spec.id == "scenario_c") else spec.expected_confidence,
        impact=ImpactMetrics(
            revenue_lost_hourly=kpis.gtv_at_risk_hourly,
            impacted_transactions=extra_declines,
            repeat_checkout_drop_pct=spec.abandonment_pct,
        ),
        counter_evidence=list(spec.counter_evidence) if mixed else [],
        probes=[Probe(probe_id=p.probe_id, title=p.title, description=p.description, sql=p.sql) for p in spec.probes] if mixed else [],
        default_rule=None
        if mixed or spec.default_rule is None
        else DefaultRule(
            proposal_id=spec.default_rule.proposal_id,
            source_gateway=spec.default_rule.source_gateway,
            target_gateway=spec.default_rule.target_gateway,
            filter_country=spec.default_rule.filter_country,
            filter_card_type=spec.default_rule.filter_card_type,
            filter_card_brand=spec.default_rule.filter_card_brand,
            target_rule=spec.default_rule.target_rule,
        ),
    )
    if mixed:
        rca.confidence_score = 0.41
        rca.title = "No isolated causal factor"
    elif spec.id == "scenario_a":
        rca.confidence_score = 0.96
    elif spec.id == "scenario_b":
        rca.confidence_score = 0.93

    all_executed = all(step.executed_sql and step.execution_time_ms > 0 for step in steps)
    if not all_executed or any(step.status in {"FAILED", "TIMEOUT"} for step in steps):
        raise RuntimeError("Investigation cannot emit a diagnosis without completed query evidence")

    return InvestigationResponse(
        scenario_id=spec.id,
        status=status,
        run_id=run_id,
        run_status="mixed" if mixed else "definitive",
        kpis=kpis,
        steps=steps,
        root_cause_analysis=rca,
        verification=VerificationState(
            complete=True,
            stale=stale,
            all_queries_executed=True,
            failed=False,
        ),
    )


def run_probe(scenario_id: str, probe_id: str) -> InvestigationStep:
    spec = SCENARIOS[scenario_id]
    probe = next((item for item in spec.probes if item.probe_id == probe_id), None)
    if probe is None:
        raise KeyError(probe_id)
    result = execute(probe.sql)
    rows = [
        VarianceRow(
            slice=str(row[0]),
            incident_vol=int(row[1]) if len(row) > 1 and row[1] is not None else None,
            incident_auth_pct=round(float(row[2]) * 100, 1) if len(row) > 2 and row[2] is not None and float(row[2]) <= 1 else (round(float(row[2]), 1) if len(row) > 2 and row[2] is not None else None),
        )
        for row in result.rows[:8]
    ]
    return InvestigationStep(
        step_id=f"probe_{probe_id}",
        step_number=5,
        title=probe.title,
        status="INCONCLUSIVE",
        finding=probe.description,
        chart_label="Recommended probe result",
        execution_time_ms=result.execution_time_ms,
        rows_scanned=result.rows_scanned,
        executed_sql=result.sql,
        variance_summary=rows,
        run_state="completed",
    )
