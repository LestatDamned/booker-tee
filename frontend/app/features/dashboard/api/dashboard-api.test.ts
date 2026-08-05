import { afterEach, describe, expect, it, vi } from "vitest";

import { dashboardPayload } from "../test-support";
import { loadDashboard } from "./dashboard-api";

describe("dashboard api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("validates the dashboard response at the network boundary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(dashboardPayload))),
    );

    const result = await loadDashboard();

    expect(result.status).toBe("success");
    if (result.status === "success") {
      expect(result.dashboard.summary.profit).toBe("60000.00");
      expect(result.dashboard.attention.items[0]?.nextStepKind).toBe("review");
    }
  });

  it("rejects a malformed money contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...dashboardPayload,
            summary: { ...dashboardPayload.summary, profit: 60000 },
          }),
        ),
      ),
    );

    const result = await loadDashboard();

    expect(result).toEqual({
      status: "error",
      message: "API вернул обзор неожиданного формата.",
    });
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
