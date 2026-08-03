import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PropertiesRouteView } from "./properties";
import { loadPropertiesRoute } from "./properties-loader";

describe("properties route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads session and property directory in parallel", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse(sessionPayload));
      }
      if (url === "/api/v1/properties") {
        return Promise.resolve(jsonResponse(directoryPayload));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadPropertiesRoute(
      new Request("http://localhost/app/properties"),
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.properties.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders login when either request is unauthenticated", () => {
    render(
      <MemoryRouter>
        <PropertiesRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            properties: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/login?next=%2Fapp%2Fproperties",
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
  capabilities: { canCreate: true, readonlyReasonCode: null },
};
