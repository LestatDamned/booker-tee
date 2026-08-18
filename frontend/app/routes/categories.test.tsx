import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { directory, session } from "../features/categories/test-support";
import { CategoriesRouteView } from "./categories";
import { loadCategoriesRoute } from "./categories-loader";

describe("categories route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads session and category directory in parallel", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse(session));
      }
      if (url === "/api/v1/categories") {
        return Promise.resolve(jsonResponse(directory));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadCategoriesRoute(
      new Request("http://localhost/app/categories"),
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.categories.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("renders login when either request is unauthenticated", () => {
    render(
      <MemoryRouter>
        <CategoriesRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            categories: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/app/auth/login?next=%2Fapp%2Fcategories",
    );
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
