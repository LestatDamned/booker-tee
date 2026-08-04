import { afterEach, describe, expect, it, vi } from "vitest";

import { workspaceInvitations } from "../test-support";
import {
  createWorkspaceInvitation,
  loadWorkspaceInvitations,
  revokeWorkspaceInvitation,
} from "./workspace-invitations-api";

describe("workspace invitations API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("validates metadata without requiring a credential", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(workspaceInvitations))),
    );

    const result = await loadWorkspaceInvitations(
      workspaceInvitations.workspaceId,
    );

    expect(result).toEqual({
      status: "success",
      invitations: workspaceInvitations,
    });
  });

  it("sends idempotency, CSRF and returns the transient share URL", async () => {
    const payload = {
      invitation: workspaceInvitations.items[0],
      invitations: workspaceInvitations,
      shareUrl: "https://example.test/workspaces/invitations/secret",
      replayed: false,
    };
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(payload, 201)));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createWorkspaceInvitation({
      csrfToken: "csrf",
      idempotencyKey: "f495db09-e1fe-466a-adcb-c9951356367d",
      role: "viewer",
      workspaceId: workspaceInvitations.workspaceId,
    });

    expect(result).toEqual({ status: "success", ...payload });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/workspaces/${workspaceInvitations.workspaceId}/invitations`,
      expect.objectContaining({
        body: JSON.stringify({ role: "viewer" }),
        headers: expect.objectContaining({
          "Idempotency-Key": "f495db09-e1fe-466a-adcb-c9951356367d",
          "X-CSRF-Token": "csrf",
        }),
        method: "POST",
      }),
    );
  });

  it("sends the invitation timestamp when revoking", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse({ ...workspaceInvitations, items: [] })),
    );
    vi.stubGlobal("fetch", fetchMock);
    const invitation = workspaceInvitations.items[0]!;

    await revokeWorkspaceInvitation({
      csrfToken: "csrf",
      invitation,
      workspaceId: workspaceInvitations.workspaceId,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/workspaces/${workspaceInvitations.workspaceId}/invitations/${invitation.id}/revoke`,
      expect.objectContaining({
        body: JSON.stringify({ expectedUpdatedAt: invitation.updatedAt }),
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf" }),
        method: "POST",
      }),
    );
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
