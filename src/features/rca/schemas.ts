import { z } from "zod";

export const scenarioKpisSchema = z.object({
  baseline_auth_pct: z.number(),
  incident_auth_pct: z.number(),
  delta_pct: z.number(),
  gtv_at_risk_hourly: z.number(),
});

export const scenarioSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  short_name: z.string(),
  status: z.string(),
  baseline_window: z.array(z.string()),
  anomaly_window: z.array(z.string()),
  kpis: scenarioKpisSchema,
});

export const varianceRowSchema = z.object({
  slice: z.string(),
  baseline_vol: z.number().nullable().optional(),
  baseline_auth_pct: z.number().nullable().optional(),
  incident_vol: z.number().nullable().optional(),
  incident_auth_pct: z.number().nullable().optional(),
  delta_pct: z.number().nullable().optional(),
  p_value: z.number().nullable().optional(),
  is_anomalous: z.boolean().optional(),
});

export const investigationStepSchema = z.object({
  step_id: z.string(),
  step_number: z.number(),
  title: z.string(),
  status: z.string(),
  finding: z.string(),
  chart_label: z.string(),
  execution_time_ms: z.number(),
  rows_scanned: z.number(),
  executed_sql: z.string(),
  variance_summary: z.array(varianceRowSchema),
  run_state: z.string().optional(),
});

export const investigationSchema = z.object({
  scenario_id: z.string(),
  status: z.string(),
  run_id: z.string(),
  run_status: z.string(),
  kpis: scenarioKpisSchema,
  steps: z.array(investigationStepSchema),
  root_cause_analysis: z.object({
    title: z.string(),
    culprit_trigger: z.string(),
    confidence_score: z.number(),
    impact: z.object({
      revenue_lost_hourly: z.number(),
      impacted_transactions: z.number(),
      repeat_checkout_drop_pct: z.number(),
    }),
    counter_evidence: z.array(z.string()).optional(),
    probes: z
      .array(
        z.object({
          probe_id: z.string(),
          title: z.string(),
          description: z.string(),
          sql: z.string(),
        }),
      )
      .optional(),
    default_rule: z
      .object({
        proposal_id: z.string(),
        source_gateway: z.string(),
        target_gateway: z.string(),
        filter_country: z.string().nullable().optional(),
        filter_card_type: z.string().nullable().optional(),
        filter_card_brand: z.string().nullable().optional(),
        target_rule: z.string(),
      })
      .nullable()
      .optional(),
  }),
  verification: z.object({
    complete: z.boolean(),
    stale: z.boolean(),
    all_queries_executed: z.boolean(),
    failed: z.boolean().optional(),
  }),
  planner_source: z.string().optional(),
  replan_count: z.number().optional(),
});

export const telemetrySchema = z.object({
  buckets: z.array(
    z.object({
      timestamp: z.string(),
      auth_rate: z.number(),
      baseline_auth_rate: z.number(),
      p95_latency_ms: z.number(),
      volume: z.number(),
    }),
  ),
  milestones: z.array(
    z.object({
      timestamp: z.string(),
      type: z.string(),
      label: z.string(),
      metadata: z.record(z.unknown()).optional(),
    }),
  ),
});

export const simulateSchema = z.object({
  projected_global_auth_rate: z.number(),
  projected_lift_pct: z.number(),
  recovered_revenue_hourly: z.number(),
  recovered_txns_hourly: z.number(),
  proposal_id: z.string(),
  policy_export: z.object({
    json_rule: z.record(z.unknown()),
    terraform_diff: z.string(),
    evidence_hash: z.string(),
  }),
});

export const probeResponseSchema = z.object({
  run_id: z.string(),
  probe_id: z.string(),
  node: investigationStepSchema,
});

export type InvestigationDto = z.infer<typeof investigationSchema>;
export type ScenarioSummaryDto = z.infer<typeof scenarioSummarySchema>;
export type TelemetryDto = z.infer<typeof telemetrySchema>;
export type SimulateDto = z.infer<typeof simulateSchema>;
