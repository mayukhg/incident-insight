import { describe, expect, test } from "bun:test";

import { scenarios } from "./fixtures";

describe("fixture regression", () => {
  test("preserves the three RCA outcomes", () => {
    const byId = Object.fromEntries(scenarios.map((item) => [item.id, item]));
    expect(byId["scenario_a"]?.confidence).toBe(96);
    expect(byId["scenario_a"]?.status).toBe("definitive");
    expect(byId["scenario_b"]?.confidence).toBe(93);
    expect(byId["scenario_c"]?.confidence).toBe(41);
    expect(byId["scenario_c"]?.status).toBe("mixed");
    expect(byId["scenario_c"]?.counterEvidence?.length).toBeGreaterThan(0);
    expect(byId["scenario_c"]?.probes?.every((probe) => probe.probeId)).toBe(true);
  });
});
