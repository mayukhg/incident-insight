# Payment Incident RCA Workbench

## Goal
Replace the blank starter page with a production-quality, dark, high-density payment incident investigation cockpit based on the supplied README specification. The first screen will be the working three-pane application, not a marketing page.

## Build plan

1. **Establish the product design system**
   - Define a restrained graphite/zinc workspace with emerald, rose, amber, and blue semantic states.
   - Add a compact display/body font pairing, tabular metrics, dense spacing, crisp borders, and accessible focus states.
   - Keep the interface responsive: three panes on wide screens, a practical stacked/tabbed workflow on narrower screens.

2. **Model the three investigation scenarios**
   - Create typed scenario data for the Adyen UK 3DS incident, Visa latency incident, and mixed-evidence incident.
   - Include per-node SQL, runtime, rows scanned, cohort results, chart series, evidence, confidence, impact, and remediation data.
   - Derive all visible KPIs and status states from the selected scenario so no metric is disconnected from its evidence.

3. **Build the global incident controls**
   - Add the sticky incident selector, current incident status, contextual KPI ribbon, and re-run control.
   - Animate and temporarily show an analyzing state during re-runs, then restore the scenario’s evidence-backed verdict.
   - Update auth rate, delta, and recovery figures when simulation is enabled.

4. **Build the linked three-pane cockpit**
   - **Investigation Tree:** four selectable hypothesis nodes with execution states, runtimes, rows scanned, and anomaly annotations.
   - **Proof Workbench:** node-linked syntax-highlighted SQL, copy feedback, verified execution metadata, cohort variance table, and responsive Recharts telemetry with deployment/incident markers.
   - **RCA & Action:** evidence-linked root cause, confidence visualization, risk metrics, failover switch, target routing rule, projected recovery, and export action.

5. **Implement definitive and mixed-evidence workflows**
   - For definitive scenarios, allow failover simulation and open an export modal with selectable JSON and Terraform policy formats plus copy/download actions.
   - For the mixed scenario, remove remediation controls, show an ambiguity diagnostic, list counter-evidence, and provide runnable broader-window probing queries.
   - Ensure left-node selection immediately pivots SQL, scan metadata, table rows, and chart context.

6. **Finish product details and verification**
   - Replace placeholder metadata with unique Payment Incident RCA Workbench title, description, Open Graph, and Twitter metadata on the home route.
   - Update the root README with the supplied product specification and accurate project run instructions.
   - Verify desktop and mobile layouts, scenario switching, node pivots, re-run animation, simulation updates, SQL copying, probe actions, modal behavior, exports, and error-free rendering.

## Technical approach
- Use the existing TanStack Start home route and shared root shell.
- Use React state with typed local scenario fixtures; this iteration is a demonstrable frontend cockpit and does not require a connected database.
- Reuse the installed design-system controls, Lucide icons, and Recharts rather than adding unnecessary dependencies.
- Keep visual values in semantic Tailwind v4 tokens and split the cockpit into focused components and data modules.
