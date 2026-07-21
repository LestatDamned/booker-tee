import { afterEach, describe, expect, it, vi } from "vitest";

import { loadImportReview } from "./import-review-api";
import { importReviewPayload } from "../test-support";

describe("import review API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("validates the typed review response", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(importReviewPayload()), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadImportReview(
      "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8",
    );

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/import-review/5e4c43a1-7e08-4afe-a442-5d1d72e08ca8",
      {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      },
    );
  });

  it.each([
    [401, "unauthenticated"],
    [403, "forbidden"],
    [404, "not-found"],
  ] as const)("maps HTTP %s to %s", async (httpStatus, expectedStatus) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: httpStatus }))),
    );

    await expect(
      loadImportReview("f99027d0-bb64-45e6-81d4-f3b7a9f9a39f"),
    ).resolves.toEqual({
      status: expectedStatus,
    });
  });

  it("rejects a malformed response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ queue: { total: "wrong" } }), {
            status: 200,
          }),
        ),
      ),
    );

    await expect(
      loadImportReview("f99027d0-bb64-45e6-81d4-f3b7a9f9a39f"),
    ).resolves.toEqual({
      status: "error",
      message: "API вернул данные import review неожиданного формата.",
    });
  });
});
