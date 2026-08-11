import { afterEach, describe, expect, it, vi } from "vitest";

import { operationsFixture } from "../test-support";
import { loadOperations } from "./operations-api";

describe("operations API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads and validates the unified operations contract", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(operationsFixture()), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadOperations("?source=bank_pdf&page=2");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/operations?source=bank_pdf&page=2",
      expect.any(Object),
    );
    expect(result.status).toBe("success");
    if (result.status !== "success") throw new Error("Expected operations");
    expect(result.operations.items.map((item) => item.source)).toEqual([
      "manual",
      "bank_pdf",
      "debt",
      "system",
    ]);
  });

  it("rejects an invalid provenance shape", async () => {
    const payload = operationsFixture();
    const malformed = {
      ...payload,
      items: payload.items.map((item, index) =>
        index === 1
          ? {
              ...item,
              provenance: {
                kind: "import",
                uploadedDocumentId: "not-a-uuid",
                rawTransactionId: null,
              },
            }
          : item,
      ),
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(malformed), {
            headers: { "Content-Type": "application/json" },
            status: 200,
          }),
        ),
      ),
    );

    const result = await loadOperations("");

    expect(result).toEqual({
      status: "error",
      message: "API вернул операции неожиданного формата.",
    });
  });
});
