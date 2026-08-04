import { afterEach, describe, expect, it, vi } from "vitest";

import { session, workspaceSettings } from "../test-support";
import {
  loadWorkspaceSettings,
  transitionWorkspaceLifecycle,
  updateWorkspaceSettings,
} from "./workspace-settings-api";

describe("workspace settings API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("validates a settings snapshot", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(workspaceSettings)),
    );

    const result = await loadWorkspaceSettings(workspaceSettings.workspace.id);

    expect(result).toEqual({ status: "success", settings: workspaceSettings });
  });

  it("rejects malformed lifecycle counts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          ...workspaceSettings,
          lifecycleImpact: {
            ...workspaceSettings.lifecycleImpact,
            currentSessionCount: -1,
          },
        }),
      ),
    );

    const result = await loadWorkspaceSettings(workspaceSettings.workspace.id);

    expect(result.status).toBe("error");
  });

  it("sends CSRF and the optimistic concurrency snapshot", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(workspaceSettings));
    vi.stubGlobal("fetch", fetchMock);

    const result = await updateWorkspaceSettings({
      csrfToken: "csrf-token",
      draft: {
        name: "Новый дом",
        workspaceType: "family",
        defaultCurrency: "USD",
      },
      expectedUpdatedAt: workspaceSettings.workspace.updatedAt,
      workspaceId: workspaceSettings.workspace.id,
    });

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/workspaces/${workspaceSettings.workspace.id}`,
      expect.objectContaining({
        method: "PUT",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
      }),
    );
    const options = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(JSON.parse(String(options.body))).toEqual({
      name: "Новый дом",
      workspaceType: "family",
      defaultCurrency: "USD",
      expectedUpdatedAt: workspaceSettings.workspace.updatedAt,
    });
  });

  it.each([
    [403, "forbidden"],
    [404, "not_found"],
    [409, "conflict"],
  ] as const)("maps HTTP %s to %s", async (status, expectedStatus) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(
            { error: { code: "workspace_error", message: "Недоступно." } },
            status,
          ),
        ),
    );

    const result = await updateWorkspaceSettings({
      csrfToken: "csrf-token",
      draft: {
        name: "Дом",
        workspaceType: "personal",
        defaultCurrency: "RUB",
      },
      expectedUpdatedAt: workspaceSettings.workspace.updatedAt,
      workspaceId: workspaceSettings.workspace.id,
    });

    expect(result.status).toBe(expectedStatus);
  });

  it("sends the lifecycle snapshots and validates the boundary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        session,
        impact: {
          movedSessionCount: 2,
          revokedInvitationCount: 1,
          disabledIntegrationConnectionCount: 1,
          disabledChatConversationBindingCount: 1,
          disabledChatIdentityBindingCount: 2,
          consumedChatConversationStateCount: 1,
          failedIntegrationDeliveryCount: 1,
        },
        navigationOutcome: {
          kind: "workspace_changed",
          href: "/app/workspaces",
          boundary: "hard_reload",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await transitionWorkspaceLifecycle({
      action: "deactivate",
      csrfToken: session.csrfToken,
      expectedCurrentWorkspaceId: session.workspace.id,
      expectedWorkspaceUpdatedAt: workspaceSettings.workspace.updatedAt,
      workspaceId: workspaceSettings.workspace.id,
    });

    expect(result).toEqual({ status: "success", href: "/app/workspaces" });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/workspaces/${workspaceSettings.workspace.id}/deactivate`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRF-Token": session.csrfToken }),
      }),
    );
    const options = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(JSON.parse(String(options.body))).toEqual({
      expectedCurrentWorkspaceId: session.workspace.id,
      expectedWorkspaceUpdatedAt: workspaceSettings.workspace.updatedAt,
    });
  });

  it("returns server-owned lifecycle blocking reasons", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "workspace_lifecycle_blocked",
              message: "Нужно другое пространство.",
              details: { reasonCodes: ["workspace_fallback_required"] },
            },
          },
          422,
        ),
      ),
    );

    const result = await transitionWorkspaceLifecycle({
      action: "deactivate",
      csrfToken: session.csrfToken,
      expectedCurrentWorkspaceId: session.workspace.id,
      expectedWorkspaceUpdatedAt: workspaceSettings.workspace.updatedAt,
      workspaceId: workspaceSettings.workspace.id,
    });

    expect(result).toEqual({
      status: "blocked",
      message: "Нужно другое пространство.",
      reasonCodes: ["workspace_fallback_required"],
    });
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
