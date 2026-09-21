# Frontend Architecture and Backend Integration Guide

This document is the handoff contract for implementing the Payment Incident RCA Workbench backend in Cursor. Read it together with [`BACKEND_IMPLEMENTATION.md`](BACKEND_IMPLEMENTATION.md): that document describes the analytical service and API payloads; this document explains the frontend that already exists, the behaviors that must be preserved, and the exact seams where backend data replaces fixtures.

## 1. What exists today

The application is a single-screen, evidence-first payment incident investigation cockpit built with:

- TanStack Start v1 and TanStack Router
- React 19 and TypeScript
- TanStack Query, already provided at the root
- Tailwind CSS v4 and the local design-system components
- Recharts for telemetry
- Sonner for notifications

The current experience is fully functional but deterministic. All incident data comes from `src/features/rca/scenarios.ts`; timers and browser-generated values imitate backend operations.

### Files to understand first

| File | Responsibility |
| --- | --- |
| `src/routes/index.tsx` | The `/` route, page metadata, and `Workbench` mount point. |
| `src/features/rca/Workbench.tsx` | Entire cockpit UI, local view state, interactions, and current mock actions. |
| `src/features/rca/scenarios.ts` | Shared frontend types plus three deterministic fixtures. |
| `src/routes/__root.tsx` | Root document, TanStack Query provider, global error/not-found views, and notifications. |
| `src/start.ts` | TanStack Start request middleware. Preserve the existing error and CSRF middleware. |
| `src/styles.css` | Semantic visual tokens. Backend work should not change these tokens or replace them with hardcoded colors. |

Do not introduce React Router, Next.js routes, an `App.tsx` router, or a second `/` route. TanStack Router owns routing through `src/routes`.

## 2. Frontend component map

`src/routes/index.tsx`

```text
Workbench
├── Sticky header
│   ├── Scenario selector
│   ├── Investigation status
│   ├── Re-run action
│   └── Four KPI cells
├── Desktop layout (25% / 48% / 27%)
│   ├── InvestigationTree
│   ├── Proof Workbench
│   │   ├── QueryEditor
│   │   ├── VarianceTable
│   │   └── TelemetryChart
│   └── RCA & Action
│       ├── Verdict
│       ├── ImpactMetrics
│       └── Remediation OR MixedEvidence
├── Mobile/tablet tabs
│   ├── Investigation
│   ├── Evidence
│   └── Verdict
└── ExportDialog
```

Desktop and mobile render the same data and actions. Do not build a separate mobile data flow. The responsive presentation switches at Tailwind's `xl` breakpoint.

## 3. Current data contract

The exact display types are exported by `src/features/rca/scenarios.ts`.

```ts
type EvidenceStatus = "success" | "anomaly" | "inconclusive";

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

type Scenario = {
  id: string;
  shortName: string;
  title: string;
  status: "definitive" | "mixed";
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

The backend may use numeric values and ISO timestamps internally. Add a mapper that returns this display shape rather than coupling UI components to database rows. Keep raw DTOs, display mapping, and presentation components separate.

### Recommended backend DTO improvements

Use raw values in transport responses:

- `runtimeMs: number` instead of `"118ms"`
- `rowsScanned: number` instead of `"268K rows"`
- volume counts as numbers instead of compact strings
- monetary amounts in minor currency units plus `currency`
- ISO timestamps instead of formatted window labels
- numeric `pValue`, with a separate display formatter

The mapper can preserve the current labels exactly.

## 4. Linked-state behavior that must not regress

The cockpit is one linked investigation view, not three independent panels.

1. Selecting an investigation updates the title, status, KPIs, tree, proof pane, verdict, and available actions.
2. Selecting a tree node updates all three proof elements together:
   - executed SQL;
   - cohort variance rows;
   - chart context label.
3. Starting a re-run clears any active simulation and displays analysis progress.
4. Changing investigations resets simulation and chooses an appropriate node.
5. Enabling simulation changes the KPI strip and remediation metrics together.
6. Export is disabled until a successful simulation exists.
7. A `mixed` investigation shows counter-evidence and probes instead of remediation.

Preserve the current `activeNode`, `simulated`, and `exportOpen` values as local presentation state. Move investigations, run state, probe results, simulations, and exports to TanStack Query.

## 5. Zero-speculation invariants

These rules are product behavior, not presentation preferences:

- Every diagnosis must reference completed query evidence.
- Every evidence node must include executed SQL, runtime, rows scanned, status, cohorts, and chart context.
- `p < 0.05` is the significance gate for causal isolation.
- Confidence must be at least `80` before remediation is available.
- Failed, timed-out, stale, contradictory, or incomplete evidence cannot produce a definitive verdict.
- Mixed evidence must show an ambiguity diagnostic, counter-evidence, and recommended probes.
- Mixed evidence must never show simulation or policy export.
- Simulation is a what-if operation and must never mutate live routing.
- Export creates a policy artifact; it does not activate the policy.
- Do not show `ZERO SPECULATION VERIFIED` or “Proof execution gate passed” while required evidence is queued, running, failed, or stale.

The backend, not the browser, must enforce these gates. The frontend should also hide or disable invalid actions, but client-side checks are not a security boundary.

## 6. Exact fixture replacement points

| Current location | Current behavior | Backend integration |
| --- | --- | --- |
| `Workbench.tsx` import of `scenarios` | Imports all fixture data | Import only shared display types/mappers; fetch investigation summaries and detail. |
| `scenarioId` state | Selects an in-memory fixture | Keep selected ID as view state or URL search state; use it as the detail query key. |
| `useMemo(...scenarios.find...)` | Resolves selected fixture | Replace with detail query data. |
| Scenario `<SelectItem>` values | Three hardcoded choices | Render summaries returned by the list query. |
| `rerun()` | Uses a 1.5-second timer | Start a run mutation, then poll run detail until a terminal state. |
| `runProbe()` | Copies SQL and shows a toast | Send a server-issued `probeId`; merge/invalidate returned evidence. Do not send arbitrary SQL. |
| `simulated` switch | Reveals fixed fixture values | Trigger a simulation mutation. Set local display mode only after success. |
| `ExportDialog` | Builds hardcoded JSON/Terraform | Request a verified export by investigation, proposal, and format. |
| `scenario.chart` | Uses fixture chart points | Return bucketed telemetry with the investigation detail or a dedicated query. |
| Proof badges | Always claim verification | Derive from completed, current evidence and backend verification state. |

## 7. Recommended TanStack Query shape

Create a browser-safe module such as `src/features/rca/queries.ts`:

```ts
import { queryOptions } from "@tanstack/react-query";
import { getInvestigation, listInvestigations } from "./investigations.functions";

export const investigationsQueryOptions = queryOptions({
  queryKey: ["investigations"],
  queryFn: () => listInvestigations(),
});

export const investigationQueryOptions = (investigationId: string) =>
  queryOptions({
    queryKey: ["investigations", investigationId],
    queryFn: () => getInvestigation({ data: { investigationId } }),
  });
```

In the component:

- Use `useSuspenseQuery` for the initial list and selected detail when the route prefetches those queries.
- Use `useMutation` for run, probe, simulation, and export actions.
- Use query invalidation or `setQueryData` when a run stage completes.
- Include `runId` in polling query keys.
- Stop polling on `definitive`, `mixed`, `failed`, or `cancelled`.
- Preserve the selected node if it still exists after refreshed data; otherwise select the newest completed node.

The root already provides `QueryClientProvider`; do not add a second provider.

## 8. Backend boundary for this repository

The deployable application is TanStack Start. The preferred in-repository backend is:

```text
src/features/rca/
  schemas.ts
  mappers.ts
  queries.ts
  investigations.functions.ts
  investigations.server.ts
  analysis.server.ts
  warehouse.server.ts
  policy-export.server.ts
```

- Use `createServerFn` from `@tanstack/react-start` for application-internal reads and mutations.
- Keep callable wrappers in `*.functions.ts` so components can import them safely.
- Keep database, warehouse, and provider logic in `*.server.ts`.
- Never import `*.server.ts` directly into a route or component.
- Read environment variables only inside server-function handlers or server route handlers.
- Return plain serializable DTOs.
- Call server functions from components with `useServerFn`, or through query functions that call the generated function directly.
- Keep the existing middleware in `src/start.ts`.

The REST/FastAPI design in `BACKEND_IMPLEMENTATION.md` can be implemented as a separately deployed analytical service. Python/FastAPI and DuckDB should not be placed inside the TanStack server runtime. If using that sidecar architecture:

1. TanStack server functions authenticate and authorize the application user.
2. Those server functions call the private analytical service.
3. The browser never receives warehouse credentials or calls the analytical service directly.
4. The service URL and credentials remain server-only environment variables.
5. Provider/service errors are translated to typed frontend states.

This adapter approach keeps the frontend contract unchanged and avoids browser CORS, credential, and tenant-isolation problems.

## 9. Suggested server-function contract

```ts
listInvestigations(): Promise<InvestigationSummary[]>

getInvestigation({ data: { investigationId } }): Promise<InvestigationDetail>

startInvestigation({
  data: { incidentId, baselineWindow, incidentWindow },
}): Promise<{ runId: string; status: "queued" | "running" }>

getInvestigationRun({ data: { runId } }): Promise<InvestigationRun>

runProbe({
  data: { investigationId, probeId },
}): Promise<{ runId: string; node: InvestigationNode }>

simulateRemediation({
  data: { investigationId, proposalId },
}): Promise<SimulationResult>

generatePolicyExport({
  data: { investigationId, proposalId, format },
}): Promise<{
  filename: string;
  mimeType: string;
  content: string;
  evidenceHash: string;
}>
```

Validate every input with Zod. Protected operations must validate the authenticated user and tenant on the server; never accept a browser-supplied user ID or tenant ID as authority.

## 10. UI states the backend implementation must add

The current fixture UI only models completed results. Add these states without changing the core layout:

- investigation list loading and empty;
- selected investigation loading and not found;
- run queued, running, failed, cancelled, definitive, and mixed;
- node queued, running, completed, inconclusive, failed, and timed out;
- stale evidence;
- probe running, failed, and completed;
- simulation running, unavailable, capacity failed, and completed;
- export generating and failed;
- unauthorized/session expired.

Completed node results should remain readable while a re-run is in progress, with a clear stale/running indication, rather than blanking the proof pane.

## 11. Formatting and compatibility details

- The current UI expects exactly four ordered nodes, but backend code should not rely on array positions for identity. Use stable node IDs and sequence numbers.
- `activeNode` is currently an array index. Prefer storing an `activeNodeId` during integration.
- The telemetry chart currently expects `time`, `baseline`, `incident`, and `latency` for each bucket.
- The chart currently places a marker at `14:05`; return milestone timestamps and labels so this becomes data-driven.
- `CohortRow` currently uses `0` to mean unavailable in some fixture rows. The backend DTO should use `null`, and the mapper should render an em dash.
- Current p-values are display strings. Keep numeric p-values in backend responses.
- Current export content is specific to Scenario A. Never reuse it for another investigation.
- Browser clipboard and download operations belong in event handlers and can remain client-side after content is returned securely.

## 12. Integration sequence for Cursor

1. Preserve the three fixtures as tests before changing production data flow.
2. Split display types from fixture data and add Zod schemas for transport DTOs.
3. Add mappers from backend DTOs to the current display model.
4. Implement investigation list and detail server functions.
5. Add query options and prefetch safe initial data through the route where appropriate.
6. Replace the hardcoded selector and selected fixture lookup.
7. Implement tracked investigation runs and stage polling.
8. Make verification badges depend on evidence completion and freshness.
9. Implement allowlisted probes using `probeId`.
10. Implement gated remediation simulation.
11. Generate policy exports from the verified backend proposal.
12. Add loading, failure, unauthorized, and stale states.
13. Add unit tests for gates/mappers and integration tests for all three scenarios.

## 13. Acceptance checklist

- Page refresh preserves completed investigations and evidence.
- The selector is populated from backend summaries.
- Selecting an investigation updates every linked section.
- Selecting a node updates SQL, cohorts, and telemetry context together.
- Re-run creates a tracked run and exposes stage progress.
- Every visible diagnosis traces to completed evidence and execution metadata.
- Verification markers disappear when evidence is incomplete, failed, or stale.
- Mixed evidence never renders simulation or export controls.
- Probes use server-owned IDs and query templates.
- Simulation is rejected server-side when confidence is below 80 or evidence is invalid.
- Export content matches the selected verified proposal and contains an evidence hash.
- No payment secrets, raw sensitive records, credentials, arbitrary SQL, tenant IDs, or user IDs are trusted from the browser.
- Desktop and mobile tabs display the same backend state.
- Scenario A remains definitive at 96% confidence.
- Scenario B remains definitive at 93% confidence.
- Scenario C remains mixed at 41% confidence with counter-evidence and probes only.

## 14. Definition of done

The backend integration is complete when the fixtures are no longer used by the production path, every cockpit action uses a real tracked backend operation, all zero-speculation gates are enforced server-side, and the three deterministic scenarios pass as automated regression fixtures without visual or behavioral regression.