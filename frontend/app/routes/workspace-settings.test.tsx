import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  session,
  workspaceInvitations,
  workspaceMembers,
  workspaceSettings,
} from "../features/workspaces/test-support";
import { loadWorkspaceSettingsRoute } from "./workspace-settings-loader";
import { WorkspaceSettingsRouteView } from "./workspace-settings";

describe("workspace settings route", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads session and target workspace in parallel", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") {
        return Promise.resolve(jsonResponse(session));
      }
      if (
        String(input) === `/api/v1/workspaces/${workspaceSettings.workspace.id}`
      ) {
        return Promise.resolve(jsonResponse(workspaceSettings));
      }
      if (
        String(input) ===
        `/api/v1/workspaces/${workspaceSettings.workspace.id}/members`
      ) {
        return Promise.resolve(jsonResponse(workspaceMembers));
      }
      if (
        String(input) ===
        `/api/v1/workspaces/${workspaceSettings.workspace.id}/invitations`
      ) {
        return Promise.resolve(jsonResponse(workspaceInvitations));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadWorkspaceSettingsRoute(
      new Request(
        `http://localhost/app/workspaces/${workspaceSettings.workspace.id}/settings`,
      ),
      workspaceSettings.workspace.id,
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.settings.status).toBe("success");
    expect(result.members?.status).toBe("success");
    expect(result.invitations?.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("does not request the private team directory without capability", async () => {
    const readonlySettings = {
      ...workspaceSettings,
      workspace: {
        ...workspaceSettings.workspace,
        capabilities: {
          ...workspaceSettings.workspace.capabilities,
          canViewMemberDirectory: false,
          canViewWorkspaceActivity: false,
        },
      },
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") {
        return Promise.resolve(jsonResponse(session));
      }
      if (
        String(input) === `/api/v1/workspaces/${workspaceSettings.workspace.id}`
      ) {
        return Promise.resolve(jsonResponse(readonlySettings));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadWorkspaceSettingsRoute(
      new Request(
        `http://localhost/app/workspaces/${workspaceSettings.workspace.id}/settings`,
      ),
      workspaceSettings.workspace.id,
    );

    expect(result.members).toBeNull();
    expect(result.invitations).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("uses one masked not-found state", () => {
    render(
      <MemoryRouter>
        <WorkspaceSettingsRouteView
          loaderData={{
            session: { status: "authenticated", session },
            settings: { status: "not_found" },
            members: null,
            invitations: null,
          }}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "Такого пространства нет" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Рабочие пространства" }),
    ).toHaveAttribute("href", "/app/workspaces");
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
