# 🛠️ Backend Implementation & Frontend Integration Guide

> **System Target:** Deterministic Payments Root-Cause Analysis (RCA) Engine & Remediation Service  
> **Guiding Principle:** Zero-Speculation. Every claim emitted by the backend must be backed by an executed SQL query, runtime audit, row scan metrics, and statistical hypothesis testing.

---

## 1. Vision & Architecture

The backend acts as the deterministic analytical core for the **Payment Incident RCA Workbench**. It accepts high-level operational questions, orchestrates a plan-first investigation DAG, executes analytical SQL queries against an embedded DuckDB transaction book, correlates operational telemetry (code deploys, configuration updates, and provider status hooks), and streams structured, auditable proof payloads to the frontend cockpit.


```

┌────────────────────────────────────────────────────────────────────────┐
│                        Frontend (Lovable Tri-Pane)                     │
│   [Investigation DAG (25%)]  [Proof Workbench (48%)]  [Cockpit (27%)]  │
└───────────────────────────────────▲────────────────────────────────────┘
│ SSE / REST API (FastAPI)
┌───────────────────────────────────┴────────────────────────────────────┐
│                       Backend Analytical Service                       │
│                                                                        │
│   ┌───────────────────────────┐      ┌───────────────────────────────┐ │
│   │   Investigation Planner   │◄─────┤   Ground-Truth Seed Engine    │ │
│   │   (Stateful Hypothesis)   │      │   (DuckDB Synthetic Ledger)   │ │
│   └─────────────┬─────────────┘      └───────────────────────────────┘ │
│                 │                                                      │
│                 ▼                                                      │
│   ┌───────────────────────────┐      ┌───────────────────────────────┐ │
│   │    DuckDB Query Gate      ├─────►│  Statistical Variance Scorer  │ │
│   │ (Execution & Audit Trace) │      │      (p-value & Shift/Lift)   │ │
│   └─────────────┬─────────────┘      └───────────────────────────────┘ │
│                 │                                                      │
│                 ▼                                                      │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │  Prescriptive Remediation & Simulation Engine (JSON/Terraform) │   │
│   └────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘

```

---

## 2. Roadmap


```

[M1: Data & Seed Engine] ──► [M2: Investigation DAG] ──► [M3: Stats & Telemetry] ──► [M4: API & Integration]
• DuckDB embedded setup      • Structured hypothesis     • Chi-Square & p-values     • REST endpoints + SSE
• 3 ground-truth scenarios   • Query execution trace     • Deploy / Outage overlay   • Tri-pane client hookup

```

### Milestone 1: High-Performance Data & Scenario Seeding
* Set up an in-memory or file-backed **DuckDB** analytical engine.
* Seed three realistic transaction books with deterministic failure signatures:
  * **Scenario A (Definitive Anomaly):** Adyen UK 3DS Timeout spike triggered by Deploy `#4481`.
  * **Scenario B (External Scheme Degradation):** Visa network-level latency ramp causing soft declines across multiple gateways.
  * **Scenario C (Mixed / Inconclusive Evidence):** Broad, uniform decline across all gateways and cards without operational or telemetry correlation.

### Milestone 2: Hypothesis Planner & Query Gate
* Implement a stateful DAG planner that builds sequential, dependent hypothesis steps.
* Enforce hard execution validation: every investigation step must execute bounded SQL and compute:
  $$\text{Auth Rate} = \frac{\sum \text{Status} = \text{'authorized'}}{\text{Total Attempts}}$$
* Capture execution metadata: latency in milliseconds, rows scanned, and cache state.

### Milestone 3: Telemetry Alignment & Statistical Variance Engine
* Run two-sample contingency tests (e.g., Pearson's Chi-Square test) to establish statistical significance ($p$-value) between baseline and anomaly windows.
* Correlate anomaly start timestamps with `system_deployments` and `gateway_incidents`.
* Build a counter-evidence generator when variance is diffuse or non-significant ($p \ge 0.05$).

### Milestone 4: Frontend API & Remediation Simulation
* Expose REST and Server-Sent Event (SSE) endpoints consumed by the tri-pane cockpit.
* Provide "What-If" routing simulation calculations estimating recovered Gross Transaction Value (GTV) and auth rate lift.
* Export executable routing configurations (JSON and Terraform syntax).

---

## 3. Database Schema (DuckDB)

```sql
-- 1. Core Transactional Ledger
CREATE TABLE IF NOT EXISTS transactions (
    txn_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    merchant_id VARCHAR NOT NULL,
    gateway_id VARCHAR NOT NULL,             -- 'adyen', 'stripe', 'checkout'
    card_brand VARCHAR NOT NULL,             -- 'visa', 'mastercard', 'amex'
    card_type VARCHAR NOT NULL,              -- 'credit', 'debit', 'prepaid'
    bin_country VARCHAR(2) NOT NULL,         -- 'GB', 'US', 'DE', etc.
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR NOT NULL,                 -- 'authorized', 'declined', 'error'
    decline_code VARCHAR,                    -- 'insufficient_funds', '3ds_timeout', 'do_not_honor', etc.
    raw_gateway_response VARCHAR,
    latency_ms INTEGER,
    three_ds_version VARCHAR
);

-- 2. System Deployment History
CREATE TABLE IF NOT EXISTS system_deployments (
    deploy_id VARCHAR PRIMARY KEY,
    service_name VARCHAR NOT NULL,           -- 'routing-engine', 'checkout-api'
    git_sha VARCHAR NOT NULL,
    deployed_at TIMESTAMP NOT NULL,
    config_changes JSON
);

-- 3. Third-Party Gateway Incidents
CREATE TABLE IF NOT EXISTS gateway_incidents (
    incident_id VARCHAR PRIMARY KEY,
    gateway_id VARCHAR NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    reported_severity VARCHAR NOT NULL,      -- 'degraded_performance', 'outage'
    description VARCHAR
);

```

---

## 4. Frontend Integration Points & API Contracts

The backend must serve the exact schemas required by the frontend tri-pane layout.

### 4.1 `GET /api/scenarios`

Populates the top navigation scenario selector.

```json
[
  {
    "id": "scenario_a",
    "name": "Auth rate dropped -5.2% on Tuesday (Adyen UK 3DS Timeout)",
    "status": "DEFINITIVE_RCA",
    "baseline_window": ["2026-09-15T12:00:00Z", "2026-09-15T14:00:00Z"],
    "anomaly_window": ["2026-09-15T14:00:00Z", "2026-09-15T16:00:00Z"],
    "kpis": {
      "baseline_auth_pct": 88.4,
      "incident_auth_pct": 83.2,
      "delta_pct": -5.2,
      "gtv_at_risk_hourly": 42000.00
    }
  },
  {
    "id": "scenario_b",
    "name": "Card Brand Visa Latency Spike & Soft Decline Ramp (-3.8%)",
    "status": "DEFINITIVE_RCA",
    "baseline_window": ["2026-09-16T08:00:00Z", "2026-09-16T10:00:00Z"],
    "anomaly_window": ["2026-09-16T10:00:00Z", "2026-09-16T12:00:00Z"],
    "kpis": {
      "baseline_auth_pct": 89.1,
      "incident_auth_pct": 85.3,
      "delta_pct": -3.8,
      "gtv_at_risk_hourly": 31000.00
    }
  },
  {
    "id": "scenario_c",
    "name": "Mixed / Inconclusive Evidence: Broad NSF Spikes Post-Holiday (-4.1%)",
    "status": "MIXED_EVIDENCE",
    "baseline_window": ["2026-09-17T09:00:00Z", "2026-09-17T11:00:00Z"],
    "anomaly_window": ["2026-09-17T11:00:00Z", "2026-09-17T13:00:00Z"],
    "kpis": {
      "baseline_auth_pct": 87.5,
      "incident_auth_pct": 83.4,
      "delta_pct": -4.1,
      "gtv_at_risk_hourly": 28000.00
    }
  }
]

```

---

### 4.2 `GET /api/investigate/{scenario_id}` or `GET /api/investigate/{scenario_id}/stream`

Supplies or streams the hypothesis steps that populate **Panel 1 (Investigation DAG)** and provide detail for **Panel 2 (Proof Workbench)**.

```json
{
  "scenario_id": "scenario_a",
  "status": "DEFINITIVE_RCA",
  "steps": [
    {
      "step_id": "step_1",
      "step_number": 1,
      "title": "Global Baseline vs Anomaly Isolation",
      "status": "ANOMALY_DETECTED",
      "execution_time_ms": 14,
      "rows_scanned": 4210500,
      "executed_sql": "SELECT COUNT(*) FILTER (WHERE status='authorized') * 1.0 / COUNT(*) AS auth_rate FROM transactions WHERE timestamp BETWEEN '2026-09-15 14:00:00' AND '2026-09-15 16:00:00';",
      "variance_summary": [
        {
          "slice": "Global Traffic",
          "baseline_vol": 124000,
          "baseline_auth_pct": 88.4,
          "incident_vol": 123800,
          "incident_auth_pct": 83.2,
          "delta_pct": -5.2,
          "p_value": 0.00001,
          "is_anomalous": true
        }
      ]
    },
    {
      "step_id": "step_2",
      "step_number": 2,
      "title": "Gateway Cohort Decomposition",
      "status": "ANOMALY_DETECTED",
      "execution_time_ms": 48,
      "rows_scanned": 4210500,
      "executed_sql": "SELECT gateway_id, COUNT(*) FILTER (WHERE status='authorized') * 1.0 / COUNT(*) AS auth_rate FROM transactions WHERE timestamp BETWEEN '2026-09-15 14:00:00' AND '2026-09-15 16:00:00' GROUP BY 1;",
      "variance_summary": [
        {
          "slice": "adyen",
          "baseline_vol": 42100,
          "baseline_auth_pct": 88.4,
          "incident_vol": 41850,
          "incident_auth_pct": 64.1,
          "delta_pct": -24.3,
          "p_value": 0.0001,
          "is_anomalous": true
        },
        {
          "slice": "stripe",
          "baseline_vol": 52000,
          "baseline_auth_pct": 88.5,
          "incident_vol": 52100,
          "incident_auth_pct": 88.1,
          "delta_pct": -0.4,
          "p_value": 0.421,
          "is_anomalous": false
        },
        {
          "slice": "checkout",
          "baseline_vol": 29900,
          "baseline_auth_pct": 88.2,
          "incident_vol": 29850,
          "incident_auth_pct": 88.0,
          "delta_pct": -0.2,
          "p_value": 0.612,
          "is_anomalous": false
        }
      ]
    },
    {
      "step_id": "step_3",
      "step_number": 3,
      "title": "Dimensional Slicing (BIN Country & Card Type on Adyen)",
      "status": "ANOMALY_DETECTED",
      "execution_time_ms": 72,
      "rows_scanned": 83950,
      "executed_sql": "SELECT bin_country, card_type, decline_code, COUNT(*) FROM transactions WHERE gateway_id = 'adyen' AND timestamp BETWEEN '2026-09-15 14:00:00' AND '2026-09-15 16:00:00' GROUP BY 1, 2, 3 ORDER BY 4 DESC LIMIT 5;",
      "variance_summary": [
        {
          "slice": "adyen / GB / Debit / 3ds_timeout",
          "baseline_vol": 18200,
          "baseline_auth_pct": 89.2,
          "incident_vol": 18100,
          "incident_auth_pct": 61.4,
          "delta_pct": -27.8,
          "p_value": 0.0001,
          "is_anomalous": true
        }
      ]
    },
    {
      "step_id": "step_4",
      "step_number": 4,
      "title": "Operational Telemetry Cross-Correlation",
      "status": "CORRELATED",
      "execution_time_ms": 12,
      "rows_scanned": 128,
      "executed_sql": "SELECT deploy_id, service_name, git_sha, deployed_at FROM system_deployments WHERE deployed_at BETWEEN '2026-09-15 13:30:00' AND '2026-09-15 14:30:00';",
      "variance_summary": []
    }
  ],
  "root_cause_analysis": {
    "title": "Adyen UK 3DS Method URL Parse Timeout",
    "culprit_trigger": "Deploy #4481 introduced a regression in handling 3DS challenge redirects at 14:02 UTC",
    "confidence_score": 0.96,
    "impact": {
      "revenue_lost_hourly": 42000.00,
      "impacted_transactions": 8420,
      "repeat_checkout_drop_pct": 14.2
    }
  }
}

```

---

### 4.3 `GET /api/telemetry/{scenario_id}`

Supplies 5-minute bucketed metrics and vertical milestone events for the **Panel 2 Telemetry Chart**.

```json
{
  "buckets": [
    {
      "timestamp": "2026-09-15T13:45:00Z",
      "auth_rate": 88.4,
      "p95_latency_ms": 285,
      "volume": 3100
    },
    {
      "timestamp": "2026-09-15T14:00:00Z",
      "auth_rate": 88.2,
      "p95_latency_ms": 290,
      "volume": 3150
    },
    {
      "timestamp": "2026-09-15T14:05:00Z",
      "auth_rate": 82.9,
      "p95_latency_ms": 1850,
      "volume": 3080
    },
    {
      "timestamp": "2026-09-15T14:10:00Z",
      "auth_rate": 83.1,
      "p95_latency_ms": 1920,
      "volume": 3120
    }
  ],
  "milestones": [
    {
      "timestamp": "2026-09-15T14:02:00Z",
      "type": "deploy",
      "label": "Deploy #4481 (routing-engine)",
      "metadata": {
        "sha": "e9a2f1b",
        "service": "routing-engine",
        "description": "Bumped 3DS challenge timeout to strict 1500ms"
      }
    }
  ]
}

```

---

### 4.4 `POST /api/remediation/simulate`

Simulates dynamic routing failover for **Panel 3 (Remediation Cockpit)**.

#### Request Body

```json
{
  "scenario_id": "scenario_a",
  "rule": {
    "source_gateway": "adyen",
    "target_gateway": "checkout",
    "filter_country": "GB",
    "filter_card_type": "debit"
  }
}

```

#### Response Body

```json
{
  "projected_global_auth_rate": 87.3,
  "projected_lift_pct": 4.1,
  "recovered_revenue_hourly": 38500.00,
  "recovered_txns_hourly": 6820,
  "policy_export": {
    "json_rule": {
      "rule_id": "dyn_failover_gb_debit_001",
      "priority": 1,
      "action": "ROUTE_OVERRIDE",
      "conditions": {
        "bin_country": "GB",
        "card_type": "debit",
        "original_gateway": "adyen"
      },
      "destination_gateway": "checkout",
      "ttl_seconds": 3600
    },
    "terraform_diff": "resource \"payment_router_override\" \"adyen_gb_debit_failover\" {\n  name        = \"Adyen GB Debit to Checkout\"\n  priority    = 1\n  destination = \"checkout\"\n  conditions  = \"country == 'GB' && card_type == 'debit'\"\n  status      = \"active\"\n}"
  }
}

```

---

## 5. Directory Layout

The backend should reside in a `backend/` directory at the project root:

```
backend/
├── main.py                  # FastAPI app definition, CORS, router registrations
├── db.py                    # DuckDB persistent/in-memory connection manager
├── seed_data.py             # Deterministic scenario dataset generator
├── requirements.txt         # Core dependencies (FastAPI, DuckDB, SciPy, etc.)
├── engine/
│   ├── __init__.py
│   ├── planner.py           # Investigation DAG & hypothesis generator
│   ├── query_gate.py        # Safe SQL execution & performance audit wrapper
│   ├── stats.py             # Contingency matrix & p-value calculators
│   └── simulator.py         # Dynamic routing failover simulation engine
└── routers/
    ├── __init__.py
    ├── scenarios.py         # /api/scenarios endpoints
    ├── investigation.py     # /api/investigate endpoints (batch & streaming)
    ├── telemetry.py         # /api/telemetry time-series endpoints
    └── remediation.py       # /api/remediation simulation & policy export

```

---

## 6. Implementation Checklist for Cursor

1. **Scaffold Directory & Dependencies**:
* Create `backend/` and install requirements: `fastapi`, `uvicorn[standard]`, `duckdb`, `pydantic>=2.0`, `scipy`, `numpy`, `sse-starlette`.


2. **Implement `seed_data.py**`:
* Write a data synthesis routine that populates `transactions`, `system_deployments`, and `gateway_incidents` with the deterministic distributions for Scenarios A, B, and C.


3. **Build Core Engine Modules**:
* `backend/db.py`: Initialize DuckDB with schemas and run `seed_data.py` on startup if tables are empty.
* `backend/engine/query_gate.py`: Wrap query executions with wall-clock timers and rows-scanned counters.
* `backend/engine/stats.py`: Compute baseline vs anomaly percentage shifts and calculate chi-square $p$-values.
* `backend/engine/simulator.py`: Calculate volume lift by simulating traffic shifts to alternate gateways.


4. **Implement REST & Streaming Routers**:
* Implement `routers/scenarios.py`, `routers/investigation.py`, `routers/telemetry.py`, and `routers/remediation.py`.


5. **Connect to Frontend**:
* Locate the frontend API service or mock state layer (`src/services/api.ts` or `src/lib/api.ts`).
* Replace static mock states with dynamic HTTP calls pointing to `http://localhost:8000`.
* Verify that clicking steps in the Investigation DAG re-queries the backend and updates the Proof Workbench in real time.
* Verify that switching to Scenario C properly renders the Mixed Evidence view and Counter-Evidence Ledger.
