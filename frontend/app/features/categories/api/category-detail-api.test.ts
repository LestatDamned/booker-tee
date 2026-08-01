import { afterEach, describe, expect, it, vi } from "vitest";

import { detail } from "../test-support";
import {
  changeCategoryLifecycle,
  deleteCategory,
  loadCategoryDetail,
  updateCategory,
} from "./category-detail-api";

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

  it("updates with CSRF, optimistic token and current detail context", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(detail)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      updateCategory({
        categoryId: detail.category.id,
        csrfToken: "csrf-token",
        draft: { name: "Еда", kind: "mixed", notes: "Покупки" },
        expectedUpdatedAt: detail.category.updatedAt,
        search: "?currency=RUB&search=market",
      }),
    ).resolves.toEqual({ status: "success", detail });

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/categories/${detail.category.id}?currency=RUB&search=market`,
      expect.objectContaining({
        body: JSON.stringify({
          name: "Еда",
          kind: "mixed",
          notes: "Покупки",
          expectedUpdatedAt: detail.category.updatedAt,
        }),
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
        method: "PUT",
      }),
    );
  });

  it("keeps update conflict recoverable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "category_update_conflict",
                message: "Категория уже изменена.",
              },
            }),
            {
              headers: { "Content-Type": "application/json" },
              status: 409,
            },
          ),
        ),
      ),
    );

    await expect(
      updateCategory({
        categoryId: detail.category.id,
        csrfToken: "csrf-token",
        draft: { name: "Еда", kind: "expense", notes: "" },
        expectedUpdatedAt: detail.category.updatedAt,
        search: "",
      }),
    ).resolves.toEqual({
      status: "conflict",
      message: "Категория уже изменена.",
    });
  });

  it("sends lifecycle tokens and validates committed impact", async () => {
    const category = {
      ...detail.category,
      isActive: false,
      capabilities: {
        ...detail.category.capabilities,
        canArchive: false,
        canRestore: true,
      },
    };
    const payload = {
      category,
      impact: {
        historyPreserved: true,
        rulesUnchanged: true,
        availableForNewReferences: false,
      },
    };
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      changeCategoryLifecycle({
        action: "archive",
        category: detail.category,
        csrfToken: "csrf-token",
      }),
    ).resolves.toEqual({ status: "success", ...payload });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/categories/${detail.category.id}/archive`,
      expect.objectContaining({
        body: JSON.stringify({
          expectedStatus: true,
          expectedUpdatedAt: detail.category.updatedAt,
        }),
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
        method: "POST",
      }),
    );
  });

  it("keeps archive blockers and deletion results explicit", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        apiErrorResponse(
          422,
          "category_archive_blocked",
          "Сначала отключите правила.",
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({ deletedId: detail.category.id, name: "Продукты" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      changeCategoryLifecycle({
        action: "archive",
        category: detail.category,
        csrfToken: "csrf-token",
      }),
    ).resolves.toEqual({
      status: "blocked",
      message: "Сначала отключите правила.",
    });
    await expect(
      deleteCategory({
        category: { ...detail.category, isActive: false },
        csrfToken: "csrf-token",
      }),
    ).resolves.toEqual({
      status: "success",
      deletedId: detail.category.id,
      name: "Продукты",
    });
    expect(fetchMock.mock.calls[1]?.[1]).toEqual(
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

function apiErrorResponse(status: number, code: string, message: string) {
  return new Response(JSON.stringify({ error: { code, message } }), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
