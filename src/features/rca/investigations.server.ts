import { fetchInvestigation, fetchScenarios, fetchTelemetry } from "./warehouse.server";
import { mapInvestigation, mapSummary } from "./mappers";
import type { Scenario } from "./types";

export async function listInvestigationsDto() {
  const summaries = await fetchScenarios();
  return summaries.map(mapSummary);
}

export async function getInvestigationDto(investigationId: string): Promise<Scenario> {
  const [summaries, detail, telemetry] = await Promise.all([
    fetchScenarios(),
    fetchInvestigation(investigationId),
    fetchTelemetry(investigationId),
  ]);
  const summary = summaries.find((item) => item.id === investigationId);
  return mapInvestigation(detail, telemetry, summary);
}
