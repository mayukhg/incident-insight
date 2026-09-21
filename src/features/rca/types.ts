export type EvidenceStatus = "success" | "anomaly" | "inconclusive";

export type CohortRow = {
  slice: string;
  baselineVolume: string;
  baselineAuth: number;
  incidentVolume: string;
  incidentAuth: number;
  delta: number;
  pValue: string;
};

export type ChartPoint = {
  time: string;
  baseline: number;
  incident: number;
  latency: number;
};

export type InvestigationNode = {
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
  stale?: boolean;
};

export type Probe = {
  probeId: string;
  title: string;
  description: string;
  sql: string;
};

export type Scenario = {
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
  probes?: Probe[];
  proposalId?: string;
  evidenceVerified: boolean;
  stale: boolean;
  markerTime: string;
  markerLabel: string;
  runId: string;
  runStatus: string;
  plannerSource?: string;
  replanCount?: number;
};

export type InvestigationSummary = {
  id: string;
  name: string;
  shortName: string;
  status: "definitive" | "mixed";
};

export type SimulationView = {
  projectedAuth: number;
  recoveredGtv: string;
  json: string;
  terraform: string;
  evidenceHash: string;
  proposalId: string;
};
