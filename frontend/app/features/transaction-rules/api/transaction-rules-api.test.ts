import { afterEach, describe, expect, it, vi } from "vitest";

import { directory } from "../test-support";
import { loadTransactionRules } from "./transaction-rules-api";

describe("transaction rules API adapter", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("validates the generated directory contract at runtime", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(directory)));
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadTransactionRules("?status=active&page=2");

    expect(result).toEqual({ status: "success", directory });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/transaction-rules?status=active&page=2",
      expect.anything(),
    );
  });

  it("rejects a malformed money projection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...directory,
            items: [
              {
                ...directory.items[0],
                condition: { ...directory.items[0]!.condition, amountMin: 100 },
              },
            ],
          }),
        ),
      ),
    );

    await expect(loadTransactionRules("")).resolves.toEqual({
      status: "error",
      message: "API вернул список правил неожиданного формата.",
    });
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
