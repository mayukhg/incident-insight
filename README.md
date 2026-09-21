# Payment Incident RCA Workbench

Autonomous, query-driven payments root-cause analysis and remediation cockpit with a strict zero-speculation guarantee: every diagnosis is linked to executed SQL evidence.

**Repository:** [github.com/mayukhg/incident-insight](https://github.com/mayukhg/incident-insight)

## Product principles

- Every hypothesis links to SQL, execution latency, rows scanned, and statistical significance.
- Cohort isolation spans gateway, card scheme, BIN country, decline code, and 3DS protocol.
- Inconclusive incidents become `MIXED_EVIDENCE` instead of speculative diagnoses.
- Verified diagnoses can feed routing failover simulation and JSON/Terraform exports.

## Cockpit

The interface is organized into three linked panes:

1. **Investigation Tree** — ordered hypothesis execution with runtime and scan metadata.
2. **Proof Workbench** — active SQL, cohort variance table, and synchronized telemetry.
3. **RCA & Action** — verdict confidence, quantified exposure, failover simulation, and policy export.

Included scenarios cover an Adyen UK debit 3DS timeout, a Checkout.com Visa latency event, and a broad mixed-evidence decline spike.

## Development

Clone the repository, install dependencies, and run the local development server:

```sh
git clone https://github.com/mayukhg/incident-insight.git
cd incident-insight
bun install
bun run dev
```

Issues and feature requests are tracked in [GitHub Issues](https://github.com/mayukhg/incident-insight/issues).

## Built with

- TanStack Start and React 19
- TypeScript
- Tailwind CSS v4
- Recharts and Radix UI
