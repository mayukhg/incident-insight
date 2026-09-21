import { exportPolicyRequest } from "./warehouse.server";
import { mapSimulation } from "./mappers";

export async function exportPolicyDto(investigationId: string, proposalId: string, format: string) {
  return mapSimulation(await exportPolicyRequest(investigationId, proposalId, format));
}
