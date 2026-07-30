import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountsRouteView } from "./accounts";
import { loadAccountsRoute } from "./accounts-loader";

describe("accounts route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads session and account directory in parallel", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse(sessionPayload));
      }
      if (url === "/api/v1/accounts") {
        return Promise.resolve(jsonResponse(directoryPayload));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadAccountsRoute(
      new Request("http://localhost/app/accounts"),
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.accounts.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders login when either request is unauthenticated", () => {
    render(
      <MemoryRouter>
        <AccountsRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            accounts: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/login?next=/app/accounts",
    );
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

const sessionPayload = {
  user: {
    id: "f4835818-f111-41d6-a59d-62f541ace357",
    email: "max@example.test",
    name: "Max",
  },
  workspace: {
    id: "c12c9ac8-6851-4467-b87a-da7fc70586c8",
    name: "Дом",
    type: "personal",
    defaultCurrency: "RUB",
  },
  membership: { role: "owner", status: "active" },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canManageMembers: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};

const directoryPayload = {
  items: [],
  accountTypes: ["cash", "card", "deposit", "checking", "other"],
  capabilities: { canCreate: true, readonlyReasonCode: null },
};
