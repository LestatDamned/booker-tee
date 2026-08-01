import { afterEach, describe, expect, it, vi } from "vitest";

import { detail } from "../test-support";
import { loadCategoryDetail } from "./category-detail-api";

describe("Category detail API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("validates detail at the network boundary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(detail))),
    );

    await expect(
      loadCategoryDetail(detail.category.id, "?currency=RUB"),
    ).resolves.toEqual({ status: "success", detail });
  });

  it("rejects malformed money and unbounded pages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...detail,
            operations: { ...detail.operations, pageSize: 101 },
          }),
        ),
      ),
    );

    await expect(loadCategoryDetail(detail.category.id, "")).resolves.toEqual({
      status: "error",
      message: "API вернул detail категории неожиданного формата.",
    });
  });

  it("keeps auth, not-found, network and HTTP states explicit", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 404 }))
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(new Response(null, { status: 400 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadCategoryDetail(detail.category.id, "")).resolves.toEqual({
      status: "unauthenticated",
    });
    await expect(loadCategoryDetail(detail.category.id, "")).resolves.toEqual({
      status: "not_found",
    });
    await expect(loadCategoryDetail(detail.category.id, "")).resolves.toEqual({
      status: "error",
      message: "Backend недоступен.",
    });
    await expect(loadCategoryDetail(detail.category.id, "")).resolves.toEqual({
      status: "error",
      message: "API вернул статус 400.",
    });
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
