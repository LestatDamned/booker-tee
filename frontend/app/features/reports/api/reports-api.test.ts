import { afterEach, describe, expect, it, vi } from "vitest";

import { reportOverview } from "../test-support";
import { loadReportOverview } from "./reports-api";

describe("loadReportOverview", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards only financial filters and parses decimal strings", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(reportOverview)),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadReportOverview(
      "?date_from=2026-07-01&currency=RUB&category_sort=expense&uncategorized_page=2",
    );

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/reports?date_from=2026-07-01&currency=RUB&uncategorized_page=2",
      expect.any(Object),
    );
    if (result.status === "success") {
      expect(result.overview.summary.profit).toBe("75000.00");
    }
  });

  it("rejects mixed or malformed network data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...reportOverview,
            summary: { ...reportOverview.summary, currency: null },
          }),
        ),
      ),
    );

    await expect(loadReportOverview("")).resolves.toEqual({
      status: "error",
      message: "API вернул отчёт неожиданного формата.",
    });
  });

  it("rejects non-decimal money strings", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...reportOverview,
            propertyRows: [
              { ...reportOverview.propertyRows[0]!, profit: "not-money" },
            ],
          }),
        ),
      ),
    );

    await expect(loadReportOverview("")).resolves.toEqual({
      status: "error",
      message: "API вернул отчёт неожиданного формата.",
    });
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
