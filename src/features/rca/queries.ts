import { queryOptions } from "@tanstack/react-query";

import { getInvestigation, listInvestigations } from "./investigations.functions";

export const investigationsQueryOptions = queryOptions({
  queryKey: ["investigations"],
  queryFn: () => listInvestigations(),
  staleTime: 30_000,
});

export const investigationQueryOptions = (investigationId: string) =>
  queryOptions({
    queryKey: ["investigations", investigationId],
    queryFn: () => getInvestigation({ data: { investigationId } }),
    staleTime: 15_000,
  });
