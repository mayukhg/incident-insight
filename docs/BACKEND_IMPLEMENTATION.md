# Backend Implementation Guide for Cursor

This document is the implementation contract for replacing the Payment Incident RCA Workbench's synthetic frontend fixtures with a production backend. Preserve the current user experience and evidence-first behavior while wiring the application to real payment telemetry, query execution, incident analysis, simulation, and policy export services.

## 1. Product contract

The workbench is an evidence-backed payment incident root-cause analysis tool. It must never present a diagnosis, confidence score, impact estimate, or remediation unless the displayed evidence was produced by a completed query.

The two possible terminal states are:

- `definitive`: the evidence clears the statistical and confidence gates. A remediation simulation may be shown.
- `mixed`: the evidence is insufficient or conflicting. Remediation must remain unavailable, and the response must include counter-evidence and recommended probing queries.

Mandatory gates:

- Statistical significance: `p < 0.05` for evidence used to isolate a cause.
- RCA confidence: `confidence >= 80` before remediation is available.
- Every investigation node must include the executed SQL, runtime, rows scanned, status, cohort results, and chart context.
- Never fabricate query results, execution metadata, confidence, or causality.
- A query failure produces an explicit failed/incomplete investigation state, not a diagnosis.

## 2. Current frontend

### Runtime and routes

- Framework: TanStack Start v1, React 19, TypeScript, Vite, and Tailwind CSS v4.
- Main route: `src/routes/index.tsx` renders the workbench.
- Main interface: `src/features/rca/Workbench.tsx`.
- Synthetic data and shared frontend types: `src/features/rca/scenarios.ts`.
- Global theme and semantic tokens: `src/styles.css`.
- Root document and notifications: `src/routes/__root.tsx`.

There is currently no application backend. All investigation results are imported from `scenarios.ts`, re-running uses a 1.5-second browser timer, probing copies SQL to the clipboard, simulation uses fixed fixture values, and exports are generated in the browser.

### Three linked panes

Desktop uses a `25% / 48% / 27%` layout. Mobile exposes the same content through Investigation, Evidence, and Verdict tabs.

1. **Investigation Tree**
   - Four ordered investigation nodes.
   - Clicking a node updates the SQL, cohort table, and chart context in the proof pane.
   - Each node shows status, finding, runtime, and rows scanned.

2. **Proof Workbench**
   - Read-only executed SQL with copy action.
   - Execution metadata and the zero-speculation verification marker.
   - Cohort variance table with baseline/incident volume, authorization rates, delta, and p-value.
   - Baseline authorization, incident authorization, and latency telemetry.

3. **RCA & Action**
   - Root-cause or mixed-evidence verdict.
   - Confidence and impact metrics.
   - Definitive incidents: failover simulation and JSON/Terraform export.
   - Mixed incidents: ambiguity warning, counter-evidence ledger, and probing queries. No remediation controls.

### Current browser state

`Workbench` currently owns:

- `scenarioId`: selected incident fixture.
- `activeNode`: investigation node shown in the proof pane.
- `simulated`: whether projected remediation metrics replace incident metrics.
- `rerunning`: temporary re-run progress state.
- `exportOpen`: export dialog visibility.

When backend integration is complete, incident and analysis data should move to TanStack Query. Keep only view state such as `activeNode`, `simulated`, and `exportOpen` in the component.

## 3. Frontend data contract

Retain the existing display model or introduce a mapper that returns this shape. Do not make presentation components depend directly on database rows or provider response formats.

```ts
type EvidenceStatus = "success" | "anomaly" | "inconclusive" | "failed";

type CohortRow = {
  slice: string;
  baselineVolume: string;
  baselineAuth: number;
  incidentVolume: string;
  incidentAuth: number;
  delta: number;
  pValue: string;
};

type ChartPoint = {
  time: string;
  baseline: number;
  incident: number;
  latency: number;
};

type InvestigationNode = {
  id: string;
  step: string;
  title: string;
  finding: string;
  runtime: string;
  rows: string;
  status: EvidenceStatus;
  sql: string;
  cohorts: CohortRow[];
  chartLabel: string;
};

type Investigation = {
  id: string;
  shortName: string;
  title: string;
  status: "definitive" | "mixed" | "running" | "failed";
  baselineAuth: number;
  incidentAuth: number;
  delta: number;
  gtvRisk: string;
  window: string;
  nodes: InvestigationNode[];
  chart: ChartPoint[];
  rootCause: string;
  summary: string;
  confidence: number;
  lostTransactions: string;
  customerAbandonment: string;
  targetRule?: string;
  simulatedAuth?: number;
  recoveredGtv?: string;
  counterEvidence?: string[];
  probes?: Array<{ title: string; description: string; sql: string }>;
};
```

Prefer numeric raw values plus explicit units in backend DTOs for new work. A frontend mapper can format volumes, currency, percentages, durations, and timestamps. Existing strings are retained above because they are the current component contract.

## 4. Required backend capabilities

### 4.1 Incident list and detail

Supply the scenario selector with actual investigations and load one complete investigation on selection.

Recommended server functions:

```ts
listInvestigations(): Promise<InvestigationSummary[]>
getInvestigation({ data: { investigationId } }): Promise<Investigation>
```

The initial route can prefetch the list and selected public/demo investigation only if the data is safe for unauthenticated rendering. Production tenant data must require authentication and must not be loaded from a public route loader.

### 4.2 Run or re-run an investigation

Replace `rerun()` in `Workbench.tsx` with a server mutation:

```ts
startInvestigation({ data: { incidentId, baselineWindow, incidentWindow } }): Promise<{
  runId: string;
  status: "queued" | "running";
}>;
```

For the first implementation, poll a status function every 1–2 seconds:

```ts
getInvestigationRun({ data: { runId } }): Promise<InvestigationRun>
```

The backend should execute the four stages in order:

1. Baseline and incident-window isolation.
2. Gateway decomposition.
3. BIN country/card type/scheme/decline/3DS cohort isolation.
4. Deployment and provider-incident correlation.

Persist each node as it completes so the frontend can render partial progress. A run is `definitive` only after all evidence needed for the verdict is complete. Failed or timed-out stages must be visible and must prevent a definitive verdict.

### 4.3 Run a probing query

Replace `runProbe()` with an authenticated server mutation. Do not accept arbitrary SQL from the browser in production. The client should send a server-issued `probeId`; the backend resolves it to an allowlisted, parameterized query template.

```ts
runProbe({ data: { investigationId, probeId } }): Promise<{
  runId: string;
  node: InvestigationNode;
}>;
```

Validate tenant ownership, query type, permitted tables, date range, row limit, and execution timeout. Read-only credentials should be used for analytical queries.

### 4.4 Remediation simulation

Replace the fixed `simulatedAuth` and `recoveredGtv` values with a mutation:

```ts
simulateRemediation({ data: {
  investigationId: string;
  proposalId: string;
} }): Promise<{
  simulatedAuth: number;
  projectedLift: number;
  recoveredGtvPerHour: number;
  recoveryPercent: number;
  capacityCheck: "passed" | "failed" | "unknown";
  assumptions: string[];
}>;
```

The backend must reject simulation when:

- the investigation is not `definitive`;
- confidence is below 80;
- required evidence is missing or stale;
- the proposal does not belong to the investigation or tenant.

This remains a what-if model. It must not write to production routing systems.

### 4.5 Policy export

Generate exports from the verified backend proposal rather than from hardcoded browser values.

```ts
generatePolicyExport({ data: {
  investigationId: string;
  proposalId: string;
  format: "json" | "terraform";
} }): Promise<{
  filename: string;
  mimeType: string;
  content: string;
  evidenceHash: string;
}>;
```

Exports must include the exact cohort match, destination route, enabled state, priority, expiry, source investigation, and immutable evidence hash. Export does not activate the rule.

## 5. Suggested persistence model

Use UUID primary keys and tenant scoping on every production table. Names may be adapted to the existing platform, but preserve these responsibilities.

### Source/telemetry tables

#### `transactions`

- `id`
- `tenant_id`
- `occurred_at`
- `merchant_id`
- `gateway_id`
- `amount_minor`
- `currency`
- `status`
- `card_brand`
- `card_type`
- `bin_country`
- `issuer_bin` or a privacy-safe issuer identifier
- `decline_code`
- `three_ds_version`
- `latency_ms`

#### `system_deployments`

- `id`, `tenant_id`, `deploy_id`
- `service_name`, `git_sha`, `deployed_at`
- `config_changes` as JSON

#### `gateway_incidents`

- `id`, `tenant_id`, `gateway_id`
- `provider_incident_id`
- `started_at`, `ended_at`
- `status`, `summary`, `raw_reference`

### Analysis tables

#### `investigations`

- incident identity, tenant, title, incident/baseline windows
- lifecycle status
- baseline/incident authorization metrics and impact metrics
- root-cause classification, evidence-backed summary, confidence
- created/updated/completed timestamps and analysis version

#### `investigation_nodes`

- investigation ID, sequence, node key/title/status/finding
- query template/version and rendered SQL snapshot
- runtime, rows scanned, result checksum
- started/completed timestamps and error details

#### `cohort_results`

- node ID, slice dimensions, volumes, authorization rates, delta, p-value

#### `telemetry_points`

- investigation ID, timestamp bucket, baseline auth, incident auth, latency

#### `counter_evidence`

- investigation ID, statement, supporting node/result reference

#### `probe_definitions` and `probe_runs`

- allowlisted probe identity, description, query template/version
- execution status and evidence output

#### `remediation_proposals` and `simulation_runs`

- investigation ID, proposed match/action, assumptions
- projected metrics, capacity result, model version, evidence hash

#### `policy_exports`

- proposal ID, format, content checksum, evidence hash, creator, timestamp

For large transaction volumes, keep raw ledger and telemetry data in the analytical warehouse. Store investigation metadata and normalized result snapshots in the application database. Do not copy unrestricted payment records into the browser.

## 6. Integration map

| Frontend location | Current behavior | Backend replacement |
| --- | --- | --- |
| Scenario selector in `Workbench` | Reads `scenarios` fixture | `listInvestigations` + `getInvestigation` |
| `changeScenario()` | Switches local fixture | Navigate/select ID and fetch cached investigation |
| `rerun()` | Browser timer and success toast | `startInvestigation`, then poll `getInvestigationRun` |
| `InvestigationTree` | Reads fixture nodes | Render persisted stage statuses/results |
| `QueryEditor` | Displays fixture SQL | Display immutable executed SQL snapshot and metadata |
| `VarianceTable` | Displays fixture cohorts | Render normalized cohort query results |
| `TelemetryChart` | Displays fixture points | Fetch bucketed auth and latency telemetry |
| `Verdict` | Displays fixture diagnosis | Render only backend verdict tied to evidence IDs/checksums |
| `runProbe()` | Copies SQL | Send allowlisted `probeId`; append returned evidence |
| Remediation switch | Toggles fixed values | Call `simulateRemediation`; show loading/error/capacity state |
| `ExportDialog` | Hardcoded JSON/Terraform | Call `generatePolicyExport` and download returned content |

## 7. Server boundaries and security

- Implement app-internal operations with TanStack Start `createServerFn` from `@tanstack/react-start`.
- Put server-callable wrappers in client-safe `*.functions.ts` files and server-only query/provider code in `*.server.ts` files.
- Read secrets inside server handlers, never in browser code or at module scope.
- Require authentication for tenant payment data, investigation execution, probes, simulation, and exports.
- Enforce tenant access server-side on every request; never trust a browser-supplied tenant or user ID.
- Use row-level access policies if Lovable Cloud is selected for persistence.
- Use separate read-only warehouse credentials for analysis and narrowly scoped credentials for application writes.
- Parameterize queries. Never concatenate user input into SQL.
- Apply maximum date ranges, row limits, execution timeouts, cancellation, and concurrency controls.
- Store only privacy-safe payment dimensions. Do not expose PAN, CVV, secrets, raw authorization payloads, or unnecessary customer identifiers.
- Log actor, tenant, run ID, query version, evidence checksum, model version, and export action for auditability.
- Return sanitized user-facing errors while retaining detailed server logs.
- Never use privileged credentials to bypass authorization checks.

## 8. Analysis pipeline

Use deterministic computation for metrics, cohort tests, correlations, and gates. If an AI model is later used to summarize evidence, it may only summarize structured query results and must cite the supporting node IDs. It must not create metrics, causes, or remediation proposals that are absent from evidence.

Recommended pipeline:

1. Validate incident and baseline windows.
2. Create an investigation run and immutable input snapshot.
3. Execute the baseline query and persist execution metadata/results.
4. Execute gateway decomposition.
5. Execute dimensional cohort slicing with minimum sample-size controls.
6. Correlate anomaly onset with deployments and gateway incidents.
7. Evaluate significance and contradiction rules.
8. Produce either:
   - definitive verdict with evidence references and confidence; or
   - mixed verdict with counter-evidence and allowlisted probe recommendations.
9. Persist the analysis version and result checksums.
10. Allow simulation only when all remediation gates pass.

Confidence must be reproducible from documented inputs. Define and version the scoring formula; do not assign confidence through free-form model judgment.

## 9. Loading, empty, and failure states to add

The current interface has only a temporary re-run indicator. Backend integration must add:

- initial investigation-list loading and empty states;
- detail loading without resetting the selected node unnecessarily;
- per-node queued, running, completed, inconclusive, and failed states;
- re-run failure and retry action;
- stale-result indicator when source data or analysis version changed;
- probe running/failure/completion states;
- simulation running, capacity-failed, and unavailable states;
- export generation failure;
- session-expired/unauthorized handling.

Do not show the zero-speculation verification marker until all claims visible in the active result are backed by completed evidence.

## 10. Recommended file layout

```text
src/features/rca/
  Workbench.tsx                 # presentation and view state
  scenarios.ts                 # replace fixtures with shared DTO types/mappers
  investigations.functions.ts  # authenticated server functions
  investigations.server.ts     # orchestration and persistence
  analysis.server.ts           # deterministic analysis pipeline
  warehouse.server.ts          # read-only analytical query adapter
  schemas.ts                   # Zod input and DTO schemas
  queries.ts                   # TanStack Query options/hooks
  policy-export.server.ts      # JSON/Terraform generation
```

Adapt this layout to the chosen data provider, but keep browser-safe contracts separate from server-only code.

## 11. Implementation sequence

1. Add authentication and tenant authorization if the app will display real payment data.
2. Create the persistence schema and access policies.
3. Create Zod schemas and the frontend DTO mapper.
4. Implement investigation list/detail reads and replace the fixture selector.
5. Implement run orchestration and stage polling.
6. Connect the investigation tree, SQL, cohort table, and chart to persisted evidence.
7. Implement deterministic verdict and mixed-evidence gates.
8. Implement allowlisted probing queries.
9. Implement remediation simulation with capacity checks.
10. Move policy generation to the server.
11. Add audit logging, errors, timeouts, and cancellation.
12. Keep the three synthetic scenarios as deterministic test fixtures.

## 12. Acceptance criteria

- Refreshing the page preserves completed investigations and evidence.
- Selecting an investigation loads its complete linked view.
- Clicking a node changes SQL, cohort results, and chart context together.
- Re-running creates a real tracked run and reports each stage's state.
- Every displayed diagnosis can be traced to completed query results and execution metadata.
- A failed or incomplete query cannot produce a definitive diagnosis.
- `p >= 0.05`, contradictory evidence, or confidence below 80 produces `mixed` behavior.
- Mixed evidence never exposes simulation or policy export.
- Probe execution uses server-owned query templates, not arbitrary browser SQL.
- Simulation cannot mutate live routing and reports assumptions/capacity status.
- Export content matches the verified proposal and includes an evidence hash.
- Cross-tenant reads and writes are rejected.
- No sensitive payment data or credentials reach the browser.
- The three existing scenarios remain reproducible in automated tests.

## 13. Test fixtures

Preserve the existing three scenarios from `src/features/rca/scenarios.ts` as integration tests:

- **Adyen UK 3DS timeout:** definitive, 96% confidence, deployment correlation, remediation available.
- **Checkout.com Visa latency:** definitive, 93% confidence, provider telemetry correlation, remediation available.
- **Broad NSF spike:** mixed, 41% confidence, no isolated cause, counter-evidence and probes only.

Tests should assert the evidence gates and UI capabilities, not only snapshot the response payload.

## 14. Out of scope unless explicitly approved

- Automatically activating a production routing rule.
- Executing arbitrary SQL supplied by the browser.
- Sending full payment records to an AI model.
- Replacing deterministic statistics with model-generated conclusions.
- Showing a remediation when evidence is mixed or incomplete.
