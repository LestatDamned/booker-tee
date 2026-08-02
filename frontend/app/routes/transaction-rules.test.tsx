import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { directory, session } from "../features/transaction-rules/test-support";
import { TransactionRulesRouteView } from "./transaction-rules";
import { loadTransactionRulesRoute } from "./transaction-rules-loader";

describe("transaction rules route", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads session and normalized directory query in parallel", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session")
        return Promise.resolve(jsonResponse(session));
      if (url === "/api/v1/transaction-rules?q=ozon&status=active") {
        return Promise.resolve(jsonResponse(directory));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadTransactionRulesRoute(
      new Request(
        "http://localhost/app/rules?q=%20ozon%20&status=active&page=-1",
      ),
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.rules.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders login when either request is unauthenticated", () => {
    render(
      <MemoryRouter>
        <TransactionRulesRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            rules: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/login?next=/app/rules",
    );
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
