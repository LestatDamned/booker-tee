import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  session,
  workspaceActivity,
} from "../features/workspaces/test-support";
import { loadWorkspaceActivityRoute } from "./workspace-activity-loader";
import { WorkspaceActivityRouteView } from "./workspace-activity";

describe("workspace activity route", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads the selected scope with the session", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") {
        return Promise.resolve(jsonResponse(session));
      }
      if (
        String(input) ===
        `/api/v1/workspaces/${workspaceActivity.workspaceId}/activity?scope=finance`
      ) {
        return Promise.resolve(jsonResponse(workspaceActivity));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadWorkspaceActivityRoute(
      new Request(
        `http://localhost/app/workspaces/${workspaceActivity.workspaceId}/activity?scope=finance`,
      ),
      workspaceActivity.workspaceId,
    );

    expect(result.scope).toBe("finance");
    expect(result.session.status).toBe("authenticated");
    expect(result.activity.status).toBe("success");
  });

  it("renders a dedicated forbidden state", () => {
    render(
      <MemoryRouter>
        <WorkspaceActivityRouteView
          loaderData={{
            activity: { status: "forbidden", message: "Нет доступа." },
            scope: "all",
            session: { status: "authenticated", session },
            workspaceId: workspaceActivity.workspaceId,
          }}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "История действий недоступна" }),
    ).toBeVisible();
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
