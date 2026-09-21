# Incident Insight

Autonomous, query-driven root-cause analysis and remediation cockpit for payments engineering —
evidence-linked hypothesis planning, high-speed transactional cohort slicing, and a strict
zero-speculation guarantee.

---

## Problem statement

Payment platforms process millions of mission-critical transactions across fractured topologies:
multiple processors (Adyen, Stripe, Checkout.com), complex regional scheme rules, fluctuating
card tiers, and constantly shifting checkout service deployments. When an auth rate drops by 5%
on a Tuesday afternoon, teams are thrust into high-stakes war rooms where minutes equal tens of
thousands of dollars in lost Gross Transaction Value (GTV).

Today, payments teams already understand the domain. What they lack is an evidence-backed
artifact that stops reactive guesswork. General-purpose LLM observability tools fall flat in
this domain: they hallucinate plausible-sounding explanations without verifying ledger realities,
fail to isolate subtle multidimensional interactions (e.g., UK debit 3DS timeouts on a single
acquirer), and cannot distinguish between technical infrastructure failures and benign customer
balance exhaustion.

**The problem, concretely:** Payments engineering has no system today that (a) takes a natural
language prompt (*"Auth rate dropped 5% last Tuesday. What happened?"*) and translates it into an
ordered, bounded hypothesis tree, (b) executes deterministic SQL across granular transactional
records and decline codes, (c) computes rigorous statistical significance ($p$-values) against
historical baselines rather than guessing, (d) explicitly yields `MIXED_EVIDENCE` when data is
diffuse rather than asserting false confidence, and (e) produces verifiable, executable
remediation policies (failover routing rules) in seconds.

If the system answers without running queries, it has failed its purpose.

## Vision

**Root-cause analysis as a deterministic, query-backed proof engine, not speculative chat.**
Incident Insight provides payment engineers and operations leaders with an auditable, verifiable
cockpit that answers: *what broke, what did it cost, what proved it, and how do we mitigate it
right now?*

That means:
- An investigation pipeline that plans before it executes — breaking down triage across Gateway,
  Card Scheme, BIN Country, Decline Code, and 3DS Protocol axes.
- A hard Zero-Speculation Guarantee — every claim emitted in a diagnosis links directly to an
  executable SQL query, execution latency, row scan count, and tabular delta.
- Statistical honesty by default — if variance is uniform across all acquirers (e.g., holiday
  NSF spikes), the engine refuses to fabricate a culprit and defaults to an inconclusive
  diagnostic ledger with recommended probe queries.
- Closed-loop remediation — connecting root cause to prescriptive action by calculating
  recovered revenue in a failover simulation sandbox and generating deployable Terraform/JSON
  routing rules.

## Strategy

Three engineering commitments carry the vision into the system design in
`docs/FRONTEND_INTEGRATION_GUIDE.md` and `docs/BACKEND_IMPLEMENTATION.md`:

1. **Query execution gates the diagnosis, never the other way around.** An RCA statement
   cannot exist in isolation; it is strictly an interpretation of an executed result set.
   The analytical engine must prove an anomaly through baseline-vs-incident variance before
   synthesizing conclusions.
2. **Cartesian cohort slicing over high-level aggregates.** Macro metrics hide systemic drops.
   The engine isolates root causes by drilling into compound dimensional cuts:
   $\text{Gateway} \times \text{Card Scheme} \times \text{Country} \times \text{Error Code}$.
3. **Build the verifiable cockpit first, then the autonomous runner.** Ship the tri-pane
   visual workbench, deterministic scenario seeds, and validation contracts before layering
   in unsupervised multi-agent orchestration — ensuring every interaction is fully inspectable
   and debuggable by human operators.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| **Phase 0 — Design & Proof Contracts** | System architecture, investigation DAG layout, UI cockpit specification, and backend implementation contracts (`docs/BACKEND_IMPLEMENTATION.md`) | ✅ Done |
| **Phase 1 — Interactive UI Cockpit** | Tri-pane React 19 / TanStack workbench (Investigation DAG, Proof Workbench, RCA Action Cockpit), deterministic scenario selector, failover simulation UI | ✅ Done (see Current Implementation) |
| **Phase 2 — Embedded Data & Analytical Engine** | DuckDB in-memory transaction ledger, high-speed cohort group-by queries, two-sample chi-square significance testing, operational deploy log correlation | 🔄 In Progress (see Handoff Guides) |
| **Phase 3 — Prescriptive Failover & Webhooks** | Real-time smart router policy export (JSON/Terraform diffs), automated PagerDuty/Slack incident summaries, dynamic routing simulation engine | ⏳ Planned |
| **Phase 4 — Autonomous Multi-Agent Triage** | Model Context Protocol (MCP) server endpoints, LangGraph-driven adaptive investigation loops, proactive real-time anomaly listeners | ⏳ Backlog |

## Current implementation

**Cockpit UI** (`src/routes/`, `src/components/`):
- High-density, tri-pane master-detail cockpit built with **TanStack Start**, **React 19**,
  and **Tailwind CSS v4**.
- **Investigation Tree (Panel 1):** Interactive vertical DAG showing ordered hypothesis
  execution, node statuses (`ANOMALY_DETECTED`, `NORMAL_BASELINE`, `INCONCLUSIVE`), execution
  latencies, and scanned row counts.
- **Proof Workbench (Panel 2):** Monospace SQL editor with copy/explain tooling, cohort
  variance tables comparing baseline vs. incident windows ($p$-values, deltas), and Recharts
  dual-axis time series with deploy milestone markers.
- **RCA & Action Cockpit (Panel 3):** Root cause synthesis, confidence scoring (e.g., 96%),
  quantified GTV exposure, dynamic failover simulator with win-rate recovery projections, and
  policy export modals.
- **Pre-seeded Scenarios:**
  1. *Scenario A (Definitive Anomaly):* Adyen UK Debit 3DS Timeout spike triggered by Deploy `#4481`.
  2. *Scenario B (External Scheme Degradation):* Checkout.com Visa scheme latency ramp and soft decline spike.
  3. *Scenario C (Mixed Evidence):* Broad, uniform post-holiday NSF drop demonstrating ambiguity handling and counter-evidence logs.

**Handoff Documentation & Contracts** (`docs/`):
- `docs/FRONTEND_INTEGRATION_GUIDE.md`: Comprehensive map of UI components, reactive state flows,
  TanStack integration patterns, fixture replacement points, and regression checklists.
- `docs/BACKEND_IMPLEMENTATION.md`: Full FastAPI + DuckDB architecture, canonical relational
  schemas (`transactions`, `system_deployments`, `gateway_incidents`), API response contracts,
  and implementation roadmap.

### Known gaps and caveats (read before treating this as production-ready)

- **Frontend currently runs on deterministic fixtures.** The prototype UI renders rich, verified
  mock states (`src/lib/` or component state) matching backend contract shapes; full dynamic
  wiring to a live FastAPI/DuckDB daemon is detailed in the handoff guide.
- **Single-node DuckDB analytical scope.** DuckDB executes analytical queries with sub-second
  speed on local and synthetic parquet blocks. For enterprise deployments exceeding billions of
  rows, the query gateway should map to distributed engines (ClickHouse, Snowflake, or BigQuery).
- **Stateless Router Exports.** Policy exports (Terraform and JSON blocks) represent static
  overrides. Pushing real-time rule changes directly into production PSP routers requires dedicated
  vault credentials and change-management approval gates.

## Future roadmap (next concrete steps)

1. Scaffold the `backend/` FastAPI application using the roadmap in `docs/BACKEND_IMPLEMENTATION.md`.
2. Populate the DuckDB analytical tables (`transactions`, `system_deployments`, `gateway_incidents`)
   using a synthetic data generation script.
3. Wire the frontend TanStack Query hooks to the backend REST/SSE endpoints (`/api/investigate`,
   `/api/telemetry`, `/api/remediation/simulate`).
4. Replace in-memory scenario toggling with streaming SSE events to visualize hypothesis steps
   executing in real-time.
5. Add automated export bindings for custom gateway routing engines (e.g., AWS Route 53,
   Envoy/Kong edge proxies, or internal payment orchestrators).

---

## How to bring up the app

The cockpit runs as a local web service powered by **TanStack Start** and **Bun** (or Node.js).

**Prerequisites:** [Bun](https://bun.sh) (recommended) or [Node.js](https://nodejs.org) 18+.

**Quick start:**

```sh
# Clone the repository
git clone [https://github.com/mayukhg/incident-insight.git](https://github.com/mayukhg/incident-insight.git)
cd incident-insight

# Install dependencies
bun install   # or: npm install

# Start development server
bun run dev   # or: npm run dev

```

Then open **http://127.0.0.1:3000** (or the port shown in your terminal).

**Backend implementation & Cursor handoff:**

To implement the backend analytical service and hook it to the UI, instruct Cursor or your
agent to follow the companion implementation specifications:

```sh
# Review integration contracts and schema models
cat docs/FRONTEND_INTEGRATION_GUIDE.md
cat docs/BACKEND_IMPLEMENTATION.md

```

**Testing and validation:**

```sh
bun run lint    # runs linter across component and route trees
bun run build   # verifies production compilation and bundle integrity

```

**Issues and feature requests:** tracked via GitHub Issues.

```
