import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

const idSchema = z.object({ investigationId: z.string().min(1) });

export const listInvestigations = createServerFn({ method: "GET" }).handler(async () => {
  const { listInvestigationsDto } = await import("./investigations.server");
  return listInvestigationsDto();
});

export const getInvestigation = createServerFn({ method: "GET" })
  .validator(idSchema)
  .handler(async ({ data }) => {
    const { getInvestigationDto } = await import("./investigations.server");
    return getInvestigationDto(data.investigationId);
  });

export const startInvestigation = createServerFn({ method: "POST" })
  .validator(idSchema)
  .handler(async ({ data }) => {
    const { startRunDto } = await import("./analysis.server");
    return startRunDto(data.investigationId);
  });

export const runProbe = createServerFn({ method: "POST" })
  .validator(z.object({ investigationId: z.string().min(1), probeId: z.string().min(1) }))
  .handler(async ({ data }) => {
    const { runProbeDto } = await import("./analysis.server");
    return runProbeDto(data.investigationId, data.probeId);
  });

export const simulateRemediation = createServerFn({ method: "POST" })
  .validator(z.object({ investigationId: z.string().min(1), proposalId: z.string().optional() }))
  .handler(async ({ data }) => {
    const { simulateDto } = await import("./analysis.server");
    return simulateDto(data.investigationId, data.proposalId);
  });

export const generatePolicyExport = createServerFn({ method: "POST" })
  .validator(
    z.object({
      investigationId: z.string().min(1),
      proposalId: z.string().min(1),
      format: z.enum(["json", "terraform"]),
    }),
  )
  .handler(async ({ data }) => {
    const { exportPolicyDto } = await import("./policy-export.server");
    return exportPolicyDto(data.investigationId, data.proposalId, data.format);
  });
