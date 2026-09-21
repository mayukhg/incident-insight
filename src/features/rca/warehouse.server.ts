import {
  investigationSchema,
  probeResponseSchema,
  scenarioSummarySchema,
  simulateSchema,
  telemetrySchema,
  type InvestigationDto,
  type ScenarioSummaryDto,
  type SimulateDto,
  type TelemetryDto,
} from "./schemas";

function apiBase(): string {
  return process.env["ANALYTICAL_API_URL"] ?? "http://127.0.0.1:8000";
}

async function analyticalFetch(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (response.status === 401) {
    throw new Error("Session expired");
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Analytical service error ${response.status}`);
  }
  return response.json();
}

export async function fetchScenarios(): Promise<ScenarioSummaryDto[]> {
  return scenarioSummarySchema.array().parse(await analyticalFetch("/api/scenarios"));
}

export async function fetchInvestigation(scenarioId: string): Promise<InvestigationDto> {
  return investigationSchema.parse(await analyticalFetch(`/api/investigate/${scenarioId}`));
}

export async function fetchTelemetry(scenarioId: string): Promise<TelemetryDto> {
  return telemetrySchema.parse(await analyticalFetch(`/api/telemetry/${scenarioId}`));
}

export async function startInvestigationRun(scenarioId: string): Promise<{ run_id: string; status: string }> {
  return (await analyticalFetch(`/api/investigate/${scenarioId}/runs`, { method: "POST" })) as {
    run_id: string;
    status: string;
  };
}

export async function simulateRemediationRequest(scenarioId: string, proposalId?: string): Promise<SimulateDto> {
  return simulateSchema.parse(
    await analyticalFetch("/api/remediation/simulate", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenarioId, proposal_id: proposalId ?? null }),
    }),
  );
}

export async function exportPolicyRequest(scenarioId: string, proposalId: string, format: string): Promise<SimulateDto> {
  return simulateSchema.parse(
    await analyticalFetch("/api/remediation/export", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenarioId, proposal_id: proposalId, format }),
    }),
  );
}

export async function runProbeRequest(scenarioId: string, probeId: string) {
  return probeResponseSchema.parse(
    await analyticalFetch("/api/probes", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenarioId, probe_id: probeId }),
    }),
  );
}
