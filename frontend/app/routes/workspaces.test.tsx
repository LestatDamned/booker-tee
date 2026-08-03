import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  session,
  workspaceDirectory,
} from "../features/workspaces/test-support";
import { WorkspacesRouteView } from "./workspaces";
import { loadWorkspacesRoute } from "./workspaces-loader";

describe("workspaces route", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads session and directory in parallel", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") {
        return Promise.resolve(jsonResponse(session));
      }
      if (String(input) === "/api/v1/workspaces") {
        return Promise.resolve(jsonResponse(workspaceDirectory));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadWorkspacesRoute(
      new Request("http://localhost/app/workspaces"),
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.workspaces.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders login when either request is unauthenticated", () => {
    render(
      <MemoryRouter>
        <WorkspacesRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            workspaces: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/login?next=%2Fapp%2Fworkspaces",
    );
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
