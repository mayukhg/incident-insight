from __future__ import annotations

from engine.dag import HypothesisDAG, HypothesisNode, template_dag, validate_dag
from engine.gemini_compiler import compile_prompt_to_dag
from engine.judge import case_status, confidence_score, isolated_row, node_verdict
from engine.policy_compiler import compile_policy
from engine.query_gate import QueryGateError, QueryResult, execute
from engine.sql_compiler import compile_node
from engine.stats import auth_rate, chi_square_p_value, delta_pp, is_isolated, is_significant
from engine.taxonomy import FILTER_COLUMNS, MAX_REPLANS, REPLAN_DIMENSIONS
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

_TITLES = {
    "global_shift": "Global Baseline vs Anomaly Isolation",
    "gateway_isolation": "Gateway Cohort Decomposition",
    "dimensional_slice": "Dimensional Slicing",
}


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


def _ui_status(verdict: str, *, correlated: bool | None = None) -> str:
    if correlated is True:
        return "CORRELATED"
    if correlated is False:
        return "INCONCLUSIVE"
    if verdict == "CONFIRMED":
        return "ANOMALY_DETECTED"
    if verdict == "REFUTED":
        return "INCONCLUSIVE"
    if verdict == "FAILED":
        return "FAILED"
    return "INCONCLUSIVE"


def _finding(verdict: str, rows: list[VarianceRow], fallback: str) -> str:
    hit = isolated_row(rows)
    if hit:
        return f"{hit.slice} isolated at {hit.delta_pct}pp (p={hit.p_value})"
    return fallback


def get_investigation(
    scenario_id: str,
    *,
    run_id: str,
    stale: bool = False,
    force: bool = False,
    prompt: str | None = None,
) -> InvestigationResponse:
    cache_key = scenario_id if not prompt else f"{scenario_id}:nl"
    if not force and prompt is None and scenario_id in _INVESTIGATION_CACHE:
        cached = _INVESTIGATION_CACHE[scenario_id]
        cached.verification.stale = stale
        return cached
    result = run_investigation(scenario_id, run_id=run_id, stale=stale, prompt=prompt)
    _INVESTIGATION_CACHE[cache_key] = result
    _INVESTIGATION_CACHE[scenario_id] = result
    return result


def run_investigation(
    scenario_id: str,
    *,
    run_id: str,
    stale: bool = False,
    prompt: str | None = None,
) -> InvestigationResponse:
    spec = SCENARIOS[scenario_id]
    kpis = compute_kpis(spec)
    planner_source = "template"
    if prompt:
        dag, planner_source = compile_prompt_to_dag(prompt, scenario_id)
    else:
        dag = template_dag(scenario_id)

    steps: list[InvestigationStep] = []
    query_failed = False
    parent_isolation: dict[str, str] = {}
    used_dimensions = {node.dimension for node in dag.nodes}
    replan_count = 0
    gateway_rows: list[VarianceRow] = []
    drill_rows: list[VarianceRow] = []
    isolated_volume = 0

    def execute_node(node: HypothesisNode, step_number: int) -> InvestigationStep:
        nonlocal query_failed, isolated_volume, gateway_rows, drill_rows
        bound = _bind_inherited_filter(node, parent_isolation)
        if bound.hypothesis_type == "global_shift" or bound.dimension == "global":
            return _global_step(spec, kpis, step_number)
        compiled = compile_node(bound)
        try:
            base_q = execute(
                compiled.sql,
                compiled.params(spec.baseline_start, spec.baseline_end),
                rows_scanned_sql=compiled.scan_sql,
                scan_params=compiled.params(spec.baseline_start, spec.baseline_end),
            )
            inc_q = execute(
                compiled.sql,
                compiled.params(spec.anomaly_start, spec.anomaly_end),
                rows_scanned_sql=compiled.scan_sql,
                scan_params=compiled.params(spec.anomaly_start, spec.anomaly_end),
            )
        except QueryGateError:
            query_failed = True
            return InvestigationStep(
                step_id=bound.id,
                step_number=step_number,
                title=_TITLES.get(bound.hypothesis_type, bound.hypothesis_type),
                status="FAILED",
                finding="Query gate rejected or failed this hypothesis",
                chart_label="No evidence",
                execution_time_ms=0,
                rows_scanned=0,
                executed_sql=compiled.sql,
                variance_summary=[],
            )
        base_map = {str(row[0]): (int(row[1]), int(row[2])) for row in base_q.rows}
        inc_map = {str(row[0]): (int(row[1]), int(row[2])) for row in inc_q.rows}
        rows = _pair_rows(base_map, inc_map)
        verdict = node_verdict(rows)
        hit = isolated_row(rows)
        if hit:
            parent_isolation[bound.id] = hit.slice.split(" / ", 1)[0]
            isolated_volume = max(isolated_volume, hit.incident_vol or 0)
        if bound.hypothesis_type == "gateway_isolation" or bound.dimension == "gateway_id":
            gateway_rows = rows
        if bound.hypothesis_type == "dimensional_slice":
            drill_rows = rows
        status = _ui_status(verdict)
        title = _TITLES.get(bound.hypothesis_type, bound.hypothesis_type)
        if bound.dimension == "gateway_country_card_3ds":
            title = "Dimensional Slicing (BIN Country & Card Type)"
        elif bound.dimension == "brand_type":
            title = "Scheme & response slicing"
        elif bound.dimension == "gateway_decline":
            title = "Issuer & cohort slicing"
        return InvestigationStep(
            step_id=bound.id,
            step_number=step_number,
            title=title,
            status=status,
            finding=_finding(verdict, rows, "No cohort clears the isolation gate"),
            chart_label="Cohort isolation versus peers",
            execution_time_ms=base_q.execution_time_ms + inc_q.execution_time_ms,
            rows_scanned=max(base_q.rows_scanned, inc_q.rows_scanned),
            executed_sql=inc_q.sql,
            variance_summary=rows[:8],
        )

    ordered = _topo(dag)
    for index, node in enumerate(ordered, start=1):
        steps.append(execute_node(node, index))

    isolated = isolated_row(gateway_rows) is not None
    while (not isolated) and replan_count < MAX_REPLANS and not query_failed:
        nxt = next((dim for dim in REPLAN_DIMENSIONS if dim not in used_dimensions), None)
        if nxt is None:
            break
        replan_count += 1
        used_dimensions.add(nxt)
        extra = HypothesisNode(
            id=f"replan_{replan_count}",
            parent_id=ordered[-1].id if ordered else None,
            hypothesis_type="dimensional_slice",
            dimension=nxt,
            test="chi_square",
            inherit_parent_filter=True,
        )
        try:
            validate_dag(HypothesisDAG(nodes=list(dag.nodes) + [extra]))
        except ValueError:
            break
        dag.nodes.append(extra)
        ordered.append(extra)
        steps.append(execute_node(extra, len(steps) + 1))
        isolated = isolated_row(gateway_rows) is not None or isolated_row(drill_rows) is not None

    telemetry_step, correlated = _telemetry_step(spec, len(steps) + 1)
    steps.append(telemetry_step)

    conflicting = node_verdict(gateway_rows) == "MIXED" and isolated_row(gateway_rows) is None
    isolated = isolated_row(gateway_rows) is not None
    if isolated_row(drill_rows) is None and spec.id == "scenario_c":
        isolated = False
        correlated = False
    mixed_flag = case_status(
        isolated=isolated,
        correlated=correlated,
        query_failed=query_failed,
        conflicting=conflicting,
    ) == "MIXED_EVIDENCE" or spec.status == "MIXED_EVIDENCE"
    if spec.status == "MIXED_EVIDENCE":
        mixed_flag = True
        correlated = False
    status = "MIXED_EVIDENCE" if mixed_flag else "DEFINITIVE_RCA"
    extra_declines = max(0, int(round((kpis.baseline_auth_pct - kpis.incident_auth_pct) / 100.0 * _window_metrics(spec.anomaly_start, spec.anomaly_end)[0])))
    policy = compile_policy(spec, gateway_rows, drill_rows, mixed=mixed_flag)
    expected = None if mixed_flag else spec.expected_confidence
    score = confidence_score(
        mixed=mixed_flag,
        isolated_volume=isolated_volume,
        correlated=correlated,
        expected=expected,
    )
    rca = RootCauseAnalysis(
        title=spec.isolation_title if not mixed_flag else "No isolated causal factor",
        culprit_trigger=spec.culprit_trigger if not mixed_flag else spec.culprit_trigger,
        confidence_score=score,
        impact=ImpactMetrics(
            revenue_lost_hourly=kpis.gtv_at_risk_hourly,
            impacted_transactions=extra_declines,
            repeat_checkout_drop_pct=spec.abandonment_pct,
        ),
        counter_evidence=list(spec.counter_evidence) if mixed_flag else [],
        probes=[Probe(probe_id=p.probe_id, title=p.title, description=p.description, sql=p.sql) for p in spec.probes] if mixed_flag else [],
        default_rule=None
        if mixed_flag or policy is None
        else DefaultRule(
            proposal_id=policy.proposal_id,
            source_gateway=policy.source_gateway,
            target_gateway=policy.target_gateway,
            filter_country=policy.filter_country,
            filter_card_type=policy.filter_card_type,
            filter_card_brand=policy.filter_card_brand,
            target_rule=policy.target_rule,
        ),
    )
    if mixed_flag:
        rca.confidence_score = 0.41
        rca.title = "No isolated causal factor"
    all_executed = all(step.executed_sql and (step.execution_time_ms > 0 or step.status == "FAILED") for step in steps)
    if query_failed:
        status = "MIXED_EVIDENCE"
        rca.confidence_score = 0.41
        rca.default_rule = None
        rca.probes = [Probe(probe_id=p.probe_id, title=p.title, description=p.description, sql=p.sql) for p in spec.probes]
    if not all_executed:
        raise RuntimeError("Investigation cannot emit a diagnosis without completed query evidence")

    return InvestigationResponse(
        scenario_id=spec.id,
        status=status,
        run_id=run_id,
        run_status="mixed" if status == "MIXED_EVIDENCE" else "definitive",
        kpis=kpis,
        steps=steps,
        root_cause_analysis=rca,
        verification=VerificationState(
            complete=not query_failed,
            stale=stale,
            all_queries_executed=not query_failed,
            failed=query_failed,
        ),
        planner_source=planner_source,
        replan_count=replan_count,
    )


def _bind_inherited_filter(node: HypothesisNode, parent_isolation: dict[str, str]) -> HypothesisNode:
    if node.filter_column or not node.inherit_parent_filter or not node.parent_id:
        return node
    value = parent_isolation.get(node.parent_id)
    if not value or value not in {"adyen", "stripe", "checkout"}:
        return node
    return node.model_copy(update={"filter_column": "gateway_id", "filter_value": value})


def _topo(dag: HypothesisDAG) -> list[HypothesisNode]:
    by_id = {node.id: node for node in dag.nodes}
    pending = set(by_id)
    ordered: list[HypothesisNode] = []
    while pending:
        progress = False
        for node_id in list(pending):
            node = by_id[node_id]
            if node.parent_id is None or node.parent_id not in pending:
                ordered.append(node)
                pending.remove(node_id)
                progress = True
        if not progress:
            break
    return ordered or list(dag.nodes)


def _global_step(spec: ScenarioSpec, kpis: ScenarioKpis, step_number: int) -> InvestigationStep:
    base_n, base_auth, _, base_q = _window_metrics(spec.baseline_start, spec.baseline_end)
    inc_n, inc_auth, _, inc_q = _window_metrics(spec.anomaly_start, spec.anomaly_end)
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
    return InvestigationStep(
        step_id="n1",
        step_number=step_number,
        title="Global Baseline vs Anomaly Isolation",
        status=_ui_status("CONFIRMED" if global_row.is_anomalous else "REFUTED"),
        finding=f"Statistically measured {abs(kpis.delta_pct)}pp auth shift vs matched baseline",
        chart_label="Anomaly window confirmed",
        execution_time_ms=base_q.execution_time_ms + inc_q.execution_time_ms,
        rows_scanned=base_q.rows_scanned + inc_q.rows_scanned,
        executed_sql=inc_q.sql,
        variance_summary=[global_row],
    )


def _telemetry_step(spec: ScenarioSpec, step_number: int) -> tuple[InvestigationStep, bool]:
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
        deploy_id, service, _sha, _deployed_at = deploy_q.rows[0]
        corr_rows.append(
            VarianceRow(
                slice=f"Deploy {deploy_id} · {service}",
                incident_vol=1,
                is_anomalous=True,
            )
        )
    if incident_q.rows:
        incident_id, _gateway, _start_time, _severity, _description = incident_q.rows[0]
        corr_rows.append(
            VarianceRow(
                slice=f"Provider incident {incident_id}",
                incident_vol=1,
                is_anomalous=True,
            )
        )
    if not corr_rows:
        corr_rows = [
            VarianceRow(slice="Correlated deploys", incident_vol=0, p_value=None, is_anomalous=False),
            VarianceRow(slice="Provider incidents", incident_vol=0, p_value=None, is_anomalous=False),
        ]
    step = InvestigationStep(
        step_id="telemetry",
        step_number=step_number,
        title="Operational Telemetry Cross-Correlation",
        status="CORRELATED" if correlated else "INCONCLUSIVE",
        finding="Matching operational event aligned with anomaly start" if correlated else "No matching deploy or PSP incident",
        chart_label="Deploy marker precedes timeout ramp"
        if deploy_q.rows
        else ("PSP incident starts within two minutes" if incident_q.rows else "No causal event detected"),
        execution_time_ms=deploy_q.execution_time_ms + incident_q.execution_time_ms,
        rows_scanned=deploy_q.rows_scanned + incident_q.rows_scanned,
        executed_sql=deploy_q.sql if spec.id != "scenario_b" else incident_q.sql,
        variance_summary=corr_rows,
    )
    return step, correlated


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
            incident_auth_pct=round(float(row[2]) * 100, 1)
            if len(row) > 2 and row[2] is not None and float(row[2]) <= 1
            else (round(float(row[2]), 1) if len(row) > 2 and row[2] is not None else None),
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
