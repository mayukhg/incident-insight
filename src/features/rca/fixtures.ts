import type { ChartPoint, CohortRow, EvidenceStatus, InvestigationNode, Scenario } from "./types";

const chartA: ChartPoint[] = [
  { time: "13:40", baseline: 88.6, incident: 88.5, latency: 312 },
  { time: "13:45", baseline: 88.4, incident: 88.2, latency: 326 },
  { time: "13:50", baseline: 88.5, incident: 88.1, latency: 341 },
  { time: "13:55", baseline: 88.3, incident: 87.8, latency: 389 },
  { time: "14:00", baseline: 88.4, incident: 87.6, latency: 422 },
  { time: "14:05", baseline: 88.5, incident: 82.9, latency: 986 },
  { time: "14:10", baseline: 88.2, incident: 82.4, latency: 1240 },
  { time: "14:15", baseline: 88.6, incident: 83.1, latency: 1168 },
  { time: "14:20", baseline: 88.3, incident: 83.3, latency: 1094 },
  { time: "14:25", baseline: 88.4, incident: 83.2, latency: 1041 },
  { time: "14:30", baseline: 88.5, incident: 83.4, latency: 1018 },
];

const node = (
  id: string,
  step: string,
  title: string,
  finding: string,
  runtime: string,
  rows: string,
  status: EvidenceStatus,
  sql: string,
  cohorts: CohortRow[],
  chartLabel: string,
): InvestigationNode => ({ id, step, title, finding, runtime, rows, status, sql, cohorts, chartLabel });

const baselineSql = `WITH windows AS (\n  SELECT status, amount,\n    CASE WHEN timestamp BETWEEN TIMESTAMP '2026-09-15 14:00:00'\n      AND TIMESTAMP '2026-09-15 15:00:00' THEN 'incident' ELSE 'baseline' END AS window\n  FROM transactions\n  WHERE timestamp BETWEEN TIMESTAMP '2026-09-08 14:00:00'\n    AND TIMESTAMP '2026-09-15 15:00:00'\n)\nSELECT window, COUNT(*) AS volume,\n  AVG((status = 'authorized')::INT) AS auth_rate, SUM(amount) AS gtv\nFROM windows GROUP BY window ORDER BY window;`;

const gatewaySql = `SELECT gateway_id,\n  COUNT(*) FILTER (WHERE window = 'baseline') AS baseline_volume,\n  AVG((status = 'authorized')::INT) FILTER (WHERE window = 'baseline') AS baseline_auth,\n  COUNT(*) FILTER (WHERE window = 'incident') AS incident_volume,\n  AVG((status = 'authorized')::INT) FILTER (WHERE window = 'incident') AS incident_auth\nFROM transaction_windows\nGROUP BY gateway_id ORDER BY incident_auth ASC;`;

const sliceSql = `SELECT gateway_id, bin_country, card_type, decline_code, three_ds_version,\n  COUNT(*) AS incident_volume,\n  AVG((status = 'authorized')::INT) AS incident_auth,\n  baseline_auth, incident_auth - baseline_auth AS delta,\n  z_test_p_value(status, baseline_auth) AS p_value\nFROM transaction_windows\nWHERE gateway_id = 'adyen'\nGROUP BY ALL HAVING COUNT(*) > 500\nORDER BY delta ASC LIMIT 20;`;

const deploySql = `SELECT d.deploy_id, d.service_name, d.git_sha, d.deployed_at,\n  d.config_changes, MIN(t.timestamp) AS anomaly_start,\n  date_diff('minute', d.deployed_at, MIN(t.timestamp)) AS lag_minutes\nFROM system_deployments d\nJOIN transactions t ON t.timestamp BETWEEN d.deployed_at AND d.deployed_at + INTERVAL 15 MINUTE\nWHERE t.gateway_id = 'adyen' AND t.decline_code = '3ds_timeout'\nGROUP BY ALL ORDER BY ABS(lag_minutes) LIMIT 5;`;

const baselineRows: CohortRow[] = [
  { slice: "Baseline window", baselineVolume: "4.18M", baselineAuth: 88.4, incidentVolume: "612K", incidentAuth: 83.2, delta: -5.2, pValue: "<0.001" },
  { slice: "Expected range", baselineVolume: "4.18M", baselineAuth: 87.9, incidentVolume: "612K", incidentAuth: 83.2, delta: -4.7, pValue: "<0.001" },
];
const gatewayRows: CohortRow[] = [
  { slice: "Adyen", baselineVolume: "1.82M", baselineAuth: 88.4, incidentVolume: "268K", incidentAuth: 64.1, delta: -24.3, pValue: "<0.001" },
  { slice: "Stripe", baselineVolume: "1.51M", baselineAuth: 88.3, incidentVolume: "221K", incidentAuth: 88.1, delta: -0.2, pValue: "0.412" },
  { slice: "Checkout.com", baselineVolume: "850K", baselineAuth: 88.6, incidentVolume: "123K", incidentAuth: 88.5, delta: -0.1, pValue: "0.681" },
];
const sliceRows: CohortRow[] = [
  { slice: "GB · Debit · 3DS 2.2", baselineVolume: "384K", baselineAuth: 89.1, incidentVolume: "58K", incidentAuth: 51.7, delta: -37.4, pValue: "<0.001" },
  { slice: "GB · Credit · 3DS 2.2", baselineVolume: "201K", baselineAuth: 87.8, incidentVolume: "31K", incidentAuth: 78.4, delta: -9.4, pValue: "<0.001" },
  { slice: "DE · Debit · 3DS 2.2", baselineVolume: "176K", baselineAuth: 88.5, incidentVolume: "26K", incidentAuth: 88.0, delta: -0.5, pValue: "0.216" },
  { slice: "US · Credit · Exempt", baselineVolume: "421K", baselineAuth: 90.2, incidentVolume: "63K", incidentAuth: 90.0, delta: -0.2, pValue: "0.583" },
];
const deployRows: CohortRow[] = [
  { slice: "Deploy #4481 · post", baselineVolume: "384K", baselineAuth: 89.1, incidentVolume: "58K", incidentAuth: 51.7, delta: -37.4, pValue: "<0.001" },
  { slice: "Deploy #4481 · pre", baselineVolume: "192K", baselineAuth: 88.9, incidentVolume: "28K", incidentAuth: 88.7, delta: -0.2, pValue: "0.592" },
  { slice: "Provider incident", baselineVolume: "—", baselineAuth: 0, incidentVolume: "0 events", incidentAuth: 0, delta: 0, pValue: "n/a" },
];

function cohortAt(rows: CohortRow[], index: number): CohortRow {
  const row = rows[index];
  if (!row) throw new Error(`Missing cohort row at index ${index}`);
  return row;
}

const extras = {
  evidenceVerified: true,
  stale: false,
  markerTime: "14:05",
  markerLabel: "Deploy #4481",
  runId: "fixture",
  runStatus: "definitive",
};

const scenarioA: Scenario = {
  id: "scenario_a",
  shortName: "Scenario A · Adyen UK 3DS",
  title: "Auth rate dropped −5.2% on Tuesday",
  status: "definitive",
  baselineAuth: 88.4,
  incidentAuth: 83.2,
  delta: -5.2,
  gtvRisk: "$42,000/hr",
  window: "15 Sep · 14:00–15:00 UTC",
  chart: chartA,
  nodes: [
    node("baseline", "01", "Baseline & window isolation", "Statistically significant 5.2pp drop", "12ms", "4.2M rows", "success", baselineSql, baselineRows, "Anomaly window confirmed"),
    node("gateway", "02", "Gateway decomposition", "Adyen anomaly isolated at −24.3pp", "48ms", "4.2M rows", "anomaly", gatewaySql, gatewayRows, "Adyen diverges from peer PSPs"),
    node("slice", "03", "BIN country & card type", "UK debit + 3DS 2.2 isolated", "86ms", "1.8M rows", "anomaly", sliceSql, sliceRows, "Failure concentrated in GB debit"),
    node("deploy", "04", "Deployment cross-correlation", "Deploy #4481 matched at +3m", "118ms", "268K rows", "success", deploySql, deployRows, "Deploy marker precedes timeout ramp"),
  ],
  rootCause: "Adyen UK Debit · 3DS timeout",
  summary: "Deploy #4481 changed the routing-engine 3DS challenge timeout from 10s to 3s for GB debit traffic. Timeout declines began three minutes later; peer gateways remained within baseline.",
  confidence: 96,
  lostTransactions: "8,420 txns",
  customerAbandonment: "+14%",
  targetRule: "Route GB Debit Cards from Adyen → Checkout.com",
  simulatedAuth: 87.3,
  recoveredGtv: "$38,500/hr",
  proposalId: "gb_debit_adyen_to_checkout",
  ...extras,
};

const scenarioB: Scenario = {
  id: "scenario_b",
  shortName: "Scenario B · Visa latency",
  title: "Visa latency spike & soft decline ramp −3.8%",
  status: "definitive",
  baselineAuth: 89.0,
  incidentAuth: 85.2,
  delta: -3.8,
  gtvRisk: "$31,700/hr",
  window: "18 Sep · 09:20–10:20 UTC",
  chart: chartA.map((point, index) => ({ ...point, baseline: point.baseline + 0.6, incident: point.incident + 2.0, latency: point.latency + index * 36 })),
  nodes: [
    node("baseline", "01", "Baseline & window isolation", "3.8pp auth shift confirmed", "14ms", "3.7M rows", "success", baselineSql, [{ ...cohortAt(baselineRows, 0), baselineVolume: "3.71M", baselineAuth: 89.0, incidentVolume: "544K", incidentAuth: 85.2, delta: -3.8 }], "Anomaly window confirmed"),
    node("gateway", "02", "Gateway decomposition", "Checkout.com latency leads decline", "51ms", "3.7M rows", "anomaly", gatewaySql, [{ ...cohortAt(gatewayRows, 0), slice: "Checkout.com", baselineAuth: 89.2, incidentAuth: 74.8, delta: -14.4 }, { ...cohortAt(gatewayRows, 1) }, { ...cohortAt(gatewayRows, 2), slice: "Adyen" }], "Checkout.com diverges at 09:25"),
    node("slice", "03", "Scheme & response slicing", "Visa soft declines isolated", "92ms", "1.2M rows", "anomaly", sliceSql.replace("bin_country, card_type", "card_brand, card_type"), [{ ...cohortAt(sliceRows, 0), slice: "Visa · Credit · do_not_honor", baselineAuth: 88.7, incidentAuth: 66.2, delta: -22.5 }, { ...cohortAt(sliceRows, 1), slice: "Mastercard · Credit", delta: -0.4, incidentAuth: 88.0 }], "Visa latency and soft declines correlate"),
    node("deploy", "04", "Provider telemetry correlation", "Provider degradation matched", "126ms", "184K rows", "success", deploySql.replace("system_deployments", "gateway_incidents"), deployRows, "PSP incident starts within two minutes"),
  ],
  rootCause: "Checkout.com Visa processing latency",
  summary: "Checkout.com Visa authorization latency crossed 1.8s as soft declines ramped. Mastercard and other PSP paths remained stable; provider telemetry confirms degraded performance.",
  confidence: 93,
  lostTransactions: "6,140 txns",
  customerAbandonment: "+9%",
  targetRule: "Route Visa Credit from Checkout.com → Stripe",
  simulatedAuth: 88.1,
  recoveredGtv: "$28,900/hr",
  proposalId: "visa_credit_checkout_to_stripe",
  ...extras,
  markerLabel: "Provider incident",
};

const mixedRows: CohortRow[] = [
  { slice: "Adyen", baselineVolume: "1.54M", baselineAuth: 87.9, incidentVolume: "214K", incidentAuth: 83.7, delta: -4.2, pValue: "0.071" },
  { slice: "Stripe", baselineVolume: "1.46M", baselineAuth: 88.1, incidentVolume: "207K", incidentAuth: 84.1, delta: -4.0, pValue: "0.083" },
  { slice: "Checkout.com", baselineVolume: "912K", baselineAuth: 87.6, incidentVolume: "131K", incidentAuth: 83.5, delta: -4.1, pValue: "0.079" },
];

const scenarioC: Scenario = {
  id: "scenario_c",
  shortName: "Scenario C · Broad NSF spike",
  title: "Broad NSF spikes post-holiday −4.1%",
  status: "mixed",
  baselineAuth: 87.9,
  incidentAuth: 83.8,
  delta: -4.1,
  gtvRisk: "$35,200/hr",
  window: "02 Sep · 08:00–10:00 UTC",
  chart: chartA.map((point, index) => ({ ...point, baseline: point.baseline - 0.5, incident: 87.4 - index * 0.38, latency: 340 + index * 4 })),
  nodes: [
    node("baseline", "01", "Baseline & window isolation", "Broad 4.1pp shift detected", "13ms", "3.9M rows", "success", baselineSql, [{ ...cohortAt(baselineRows, 0), baselineVolume: "3.91M", baselineAuth: 87.9, incidentVolume: "552K", incidentAuth: 83.8, delta: -4.1, pValue: "0.058" }], "Broad shift near significance threshold"),
    node("gateway", "02", "Gateway decomposition", "Variance uniform across all PSPs", "46ms", "3.9M rows", "inconclusive", gatewaySql, mixedRows, "No gateway-specific divergence"),
    node("slice", "03", "Issuer & cohort slicing", "No cohort clears significance gate", "89ms", "3.9M rows", "inconclusive", sliceSql, mixedRows.map((row) => ({ ...row, slice: `${row.slice} · NSF`, delta: row.delta + 0.1 })), "Insufficient_funds distributed uniformly"),
    node("deploy", "04", "Telemetry cross-correlation", "No matching deploy or PSP incident", "121ms", "552K rows", "inconclusive", deploySql, [{ ...cohortAt(deployRows, 2), slice: "Correlated deploys", incidentVolume: "0 events" }, { ...cohortAt(deployRows, 2), slice: "Provider incidents", incidentVolume: "0 events" }], "No causal event detected"),
  ],
  rootCause: "No isolated causal factor",
  summary: "The observed decline increase is distributed across gateways, issuers, and card cohorts. No deployment or provider event aligns with the anomaly window.",
  confidence: 41,
  lostTransactions: "7,030 txns",
  customerAbandonment: "+6%",
  counterEvidence: [
    "Decline variance is uniform across Adyen, Stripe, and Checkout.com.",
    "No gateway slice passes the p < 0.05 significance gate.",
    "No deployment, configuration change, or provider incident overlaps the window.",
  ],
  probes: [
    { probeId: "expand_28d_baseline", title: "Expand to 28-day baseline", description: "Control for post-holiday issuer behavior.", sql: "SELECT issuer_country, date_trunc('day', timestamp), AVG(status='authorized') FROM transactions WHERE timestamp >= current_date - INTERVAL 28 DAY GROUP BY ALL;" },
    { probeId: "segment_issuer_bin", title: "Segment by issuer BIN", description: "Search for low-volume issuer clusters.", sql: "SELECT bin_country, card_brand, decline_code, COUNT(*), AVG(status='authorized') FROM transactions GROUP BY ALL HAVING COUNT(*) > 100;" },
    { probeId: "compare_merchant_mix", title: "Compare merchant mix", description: "Test whether portfolio composition shifted.", sql: "SELECT merchant_id, COUNT(*) volume, AVG(status='authorized') auth_rate FROM transactions GROUP BY merchant_id ORDER BY volume DESC;" },
  ],
  ...extras,
  evidenceVerified: true,
  markerLabel: "Observed shift",
  runStatus: "mixed",
};

export const scenarios: Scenario[] = [scenarioA, scenarioB, scenarioC];
