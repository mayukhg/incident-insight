import { runProbeRequest, simulateRemediationRequest, startInvestigationRun } from "./warehouse.server";
import { mapSimulation } from "./mappers";

export async function startRunDto(investigationId: string) {
  return startInvestigationRun(investigationId);
}

export async function runProbeDto(investigationId: string, probeId: string) {
  return runProbeRequest(investigationId, probeId);
}

export async function simulateDto(investigationId: string, proposalId?: string) {
  return mapSimulation(await simulateRemediationRequest(investigationId, proposalId));
}

export async function compileFromPromptDto(investigationId: string, prompt: string) {
  const { compileFromPromptRequest } = await import("./warehouse.server");
  const { mapInvestigation } = await import("./mappers");
  const { fetchScenarios, fetchTelemetry } = await import("./warehouse.server");
  const [summaries, detail, telemetry] = await Promise.all([
    fetchScenarios(),
    compileFromPromptRequest(investigationId, prompt),
    fetchTelemetry(investigationId),
  ]);
  const summary = summaries.find((item) => item.id === investigationId);
  return mapInvestigation(detail, telemetry, summary);
}

export async function approveDto(investigationId: string, proposalId: string, evidenceHash: string) {
  const { approveRemediationRequest } = await import("./warehouse.server");
  return approveRemediationRequest(investigationId, proposalId, evidenceHash);
}
