from __future__ import annotations

from engine.query_gate import execute
from models import TelemetryBucket, TelemetryMilestone, TelemetryResponse
from seed_data import SCENARIOS, iso_z


def load_telemetry(scenario_id: str) -> TelemetryResponse:
    spec = SCENARIOS[scenario_id]
    buckets_q = execute(
        """
        SELECT time_bucket(INTERVAL '5 minutes', timestamp) AS bucket,
               COUNT(*) FILTER (WHERE status = 'authorized') * 100.0 / COUNT(*) AS auth_rate,
               quantile_cont(latency_ms, 0.95) AS p95_latency_ms,
               COUNT(*) AS volume
        FROM transactions
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY 1
        ORDER BY 1
        """,
        [spec.telemetry_start, spec.anomaly_end],
        rows_scanned_sql="SELECT COUNT(*) FROM transactions WHERE timestamp >= ? AND timestamp < ?",
    )
    baseline = execute(
        """
        SELECT COUNT(*) FILTER (WHERE status = 'authorized') * 100.0 / COUNT(*) AS auth_rate
        FROM transactions
        WHERE timestamp >= ? AND timestamp < ?
        """,
        [spec.baseline_start, spec.baseline_end],
    )
    baseline_rate = round(float(baseline.rows[0][0]), 1) if baseline.rows else 0.0
    buckets = [
        TelemetryBucket(
            timestamp=row[0].strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(row[0], "strftime") else str(row[0]),
            auth_rate=round(float(row[1]), 1),
            baseline_auth_rate=baseline_rate,
            p95_latency_ms=round(float(row[2] or 0), 1),
            volume=int(row[3]),
        )
        for row in buckets_q.rows
    ]
    milestones: list[TelemetryMilestone] = []
    deploys = execute(
        """
        SELECT deploy_id, service_name, git_sha, deployed_at, CAST(config_changes AS VARCHAR)
        FROM system_deployments
        WHERE deployed_at BETWEEN CAST(? AS TIMESTAMP) - INTERVAL 20 MINUTE AND CAST(? AS TIMESTAMP)
        """,
        [spec.anomaly_start, spec.anomaly_end],
    )
    for deploy_id, service, sha, deployed_at, changes in deploys.rows:
        milestones.append(
            TelemetryMilestone(
                timestamp=deployed_at.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(deployed_at, "strftime") else str(deployed_at),
                type="deploy",
                label=f"Deploy {str(deploy_id).replace('deploy-', '#')} ({service})",
                metadata={"sha": sha, "service": service, "description": changes},
            )
        )
    incidents = execute(
        """
        SELECT incident_id, gateway_id, start_time, reported_severity, description
        FROM gateway_incidents
        WHERE start_time BETWEEN CAST(? AS TIMESTAMP) - INTERVAL 20 MINUTE AND CAST(? AS TIMESTAMP)
        """,
        [spec.anomaly_start, spec.anomaly_end],
    )
    for incident_id, gateway, start_time, severity, description in incidents.rows:
        milestones.append(
            TelemetryMilestone(
                timestamp=start_time.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(start_time, "strftime") else str(start_time),
                type="outage",
                label=f"{gateway} {severity}",
                metadata={"incident_id": incident_id, "description": description},
            )
        )
    return TelemetryResponse(buckets=buckets, milestones=milestones)
