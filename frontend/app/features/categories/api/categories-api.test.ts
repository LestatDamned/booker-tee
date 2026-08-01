import { afterEach, describe, expect, it, vi } from "vitest";

import { directory } from "../test-support";
import { createCategory, loadCategories } from "./categories-api";

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

  it("creates a category with CSRF and validates committed state", async () => {
    const committed = {
      ...directory.items[0]!,
      id: "af9366b6-8948-4a96-9280-7ee97712a50a",
      name: "Питомцы",
      notes: "Корм и ветеринар",
    };
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(committed, 201)),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createCategory({
        csrfToken: "csrf-token",
        draft: {
          name: "Питомцы",
          kind: "expense",
          notes: "Корм и ветеринар",
        },
      }),
    ).resolves.toEqual({ status: "success", category: committed });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/categories",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Питомцы",
          kind: "expense",
          notes: "Корм и ветеринар",
        }),
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
      }),
    );
  });

  it("preserves create field errors and recoverable transport states", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "category_validation_error",
              message: "Категория с таким названием уже есть.",
              fieldErrors: {
                name: ["Категория с таким названием уже есть."],
              },
            },
          },
          422,
        ),
      )
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "financial_write_forbidden",
              message: "Недостаточно прав.",
            },
          },
          403,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const request = {
      csrfToken: "csrf-token",
      draft: { name: "Продукты", kind: "expense" as const, notes: "" },
    };

    await expect(createCategory(request)).resolves.toEqual({
      status: "error",
      code: "category_validation_error",
      message: "Категория с таким названием уже есть.",
      fieldErrors: { name: ["Категория с таким названием уже есть."] },
    });
    await expect(createCategory(request)).resolves.toEqual({
      status: "error",
      code: "network_error",
      message: "Backend недоступен. Проверьте соединение и повторите.",
      fieldErrors: {},
    });
    await expect(createCategory(request)).resolves.toEqual({
      status: "unauthenticated",
    });
    await expect(createCategory(request)).resolves.toEqual({
      status: "forbidden",
      message: "Недостаточно прав.",
    });
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
