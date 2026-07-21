import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ManualLedgerRouteView } from "./manual-ledger";
import { loadManualLedgerRoute } from "./manual-ledger-loader";

describe("manual ledger route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("passes the copied URL query to the ledger API", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse(sessionPayload));
      }
      if (
        url ===
        "/api/v1/manual-ledger?type=expense&page=2&operation_id=3d0ba2b5-a853-47b8-b76b-42ea6b30ce8f"
      ) {
        return Promise.resolve(jsonResponse(ledgerPayload));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadManualLedgerRoute(
      new Request(
        "http://localhost/app/ledger/manual?type=expense&page=2&operation_id=3d0ba2b5-a853-47b8-b76b-42ea6b30ce8f",
      ),
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.ledger.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("ignores the obsolete layout parameter in old links", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse(sessionPayload));
      }
      if (url === "/api/v1/manual-ledger?type=expense") {
        return Promise.resolve(jsonResponse(ledgerPayload));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadManualLedgerRoute(
      new Request(
        "http://localhost/app/ledger/manual?type=expense&layout=flat",
      ),
    );

    expect(result.ledger.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders the login state when either request is unauthenticated", () => {
    render(
      <MemoryRouter>
        <ManualLedgerRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            ledger: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "Войдите в Booker Tee" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/login?next=/app/ledger/manual",
    );
  });

  it("renders an API error without hiding its safe message", () => {
    render(
      <MemoryRouter>
        <ManualLedgerRouteView
          loaderData={{
            session: { status: "authenticated", session: sessionPayload },
            ledger: { status: "error", message: "Backend недоступен." },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Backend недоступен.");
    expect(screen.getByRole("link", { name: "Повторить" })).toHaveAttribute(
      "href",
      "http://localhost:3000/",
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
    type: "personal" as const,
    defaultCurrency: "RUB",
  },
  membership: { role: "owner" as const, status: "active" as const },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canManageMembers: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};

const ledgerPayload = {
  items: [],
  pagination: {
    page: 2,
    perPage: 50,
    total: 0,
    totalPages: 1,
    hasPrevious: true,
    hasNext: false,
  },
  filterOptions: {
    accounts: [],
    categories: [],
    properties: [],
    perPage: [25, 50, 100, 200],
  },
  capabilities: { canCreate: true, readonlyReason: null },
  targetOperationId: "3d0ba2b5-a853-47b8-b76b-42ea6b30ce8f",
};
