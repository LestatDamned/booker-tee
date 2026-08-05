import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { dashboardPayload } from "../features/dashboard/test-support";
import { loadDashboardRoute } from "./dashboard-loader";
import { DashboardRouteView } from "./home";

describe("dashboard route", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads session and dashboard in parallel", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session")
        return Promise.resolve(jsonResponse(sessionPayload));
      if (url === "/api/v1/dashboard")
        return Promise.resolve(jsonResponse(dashboardPayload));
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadDashboardRoute(
      new Request("http://localhost/app"),
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.dashboard.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders login for an unauthenticated boundary", () => {
    render(
      <MemoryRouter>
        <DashboardRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            dashboard: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/app/auth/login?next=%2Fapp",
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
