import { afterEach, describe, expect, it, vi } from "vitest";

import { loadManualLedger } from "./manual-ledger-api";

afterEach(() => vi.unstubAllGlobals());

describe("manual ledger queries", () => {
  it("preserves route-owned search params in the API request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(validPayload()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadManualLedger("?type=expense&page=2");

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manual-ledger?type=expense&page=2",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("rejects JSON that does not satisfy the generated contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ items: "not-a-list" }), {
          status: 200,
        }),
      ),
    );

    await expect(loadManualLedger("")).resolves.toEqual({
      status: "error",
      message: "API вернул данные manual ledger неожиданного формата.",
    });
  });
});

function validPayload() {
  return {
    items: [],
    pagination: {
      page: 1,
      perPage: 50,
      total: 0,
      totalPages: 1,
      hasPrevious: false,
      hasNext: false,
    },
    filterOptions: {
      accounts: [],
      categories: [],
      properties: [],
      perPage: [25, 50, 100, 200],
    },
    capabilities: { canCreate: true, readonlyReason: null },
    targetOperationId: null,
  };
}
