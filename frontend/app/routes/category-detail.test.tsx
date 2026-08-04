import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { detail, session } from "../features/categories/test-support";
import { loadCategoryDetailRoute } from "./category-detail-loader";
import { CategoryDetailRouteView } from "./category-detail";

describe("category detail route", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads session and detail in parallel without sending return_to", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session")
        return Promise.resolve(jsonResponse(session));
      if (url.startsWith(`/api/v1/categories/${detail.category.id}`)) {
        return Promise.resolve(jsonResponse(detail));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadCategoryDetailRoute(
      new Request(
        `http://localhost/app/categories/${detail.category.id}?currency=RUB&return_to=%2Fapp%2Freports`,
      ),
      detail.category.id,
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.detail.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain(
      `/api/v1/categories/${detail.category.id}?currency=RUB`,
    );
  });

  it("renders stable unauthenticated and not-found states", () => {
    const { unmount } = render(
      <MemoryRouter>
        <CategoryDetailRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            detail: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/app/auth/login?next=%2Fapp%2Fcategories",
    );
    unmount();

    render(
      <MemoryRouter>
        <CategoryDetailRouteView
          loaderData={{
            session: { status: "authenticated", session },
            detail: { status: "not_found" },
          }}
        />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", { name: "Такой категории нет" }),
    ).toBeVisible();
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
