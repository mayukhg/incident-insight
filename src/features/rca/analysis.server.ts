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
