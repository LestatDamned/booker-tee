import { afterEach, describe, expect, it, vi } from "vitest";

import { directory } from "../test-support";
import { loadCategories } from "./categories-api";

describe("Categories API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("validates the category directory at the network boundary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(directory))),
    );

    await expect(loadCategories()).resolves.toEqual({
      status: "success",
      directory,
    });
  });

  it("rejects malformed category facts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...directory,
            items: [{ ...directory.items[0], activeRuleCount: -1 }],
          }),
        ),
      ),
    );

    await expect(loadCategories()).resolves.toEqual({
      status: "error",
      message: "API вернул список категорий неожиданного формата.",
    });
  });

  it("keeps authentication, network and HTTP failures recoverable", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadCategories()).resolves.toEqual({
      status: "unauthenticated",
    });
    await expect(loadCategories()).resolves.toEqual({
      status: "error",
      message: "Backend недоступен.",
    });
    await expect(loadCategories()).resolves.toEqual({
      status: "error",
      message: "API вернул статус 503.",
    });
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
