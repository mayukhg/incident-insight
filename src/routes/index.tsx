import { createFileRoute } from "@tanstack/react-router";
import { Workbench } from "@/features/rca/Workbench";
import { investigationsQueryOptions } from "@/features/rca/queries";

export const Route = createFileRoute("/")({
  loader: ({ context }) => context.queryClient.ensureQueryData(investigationsQueryOptions),
  head: () => ({
    meta: [
      { title: "Payment Incident RCA Workbench" },
      { name: "description", content: "Evidence-driven payment incident root-cause analysis, cohort isolation, and remediation simulation." },
      { property: "og:title", content: "Payment Incident RCA Workbench" },
      { property: "og:description", content: "Investigate payment failures with query-backed evidence and simulate safe routing remediation." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Workbench,
});
