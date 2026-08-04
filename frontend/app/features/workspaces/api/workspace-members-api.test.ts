import { afterEach, describe, expect, it, vi } from "vitest";

import { workspaceMembers } from "../test-support";
import {
  leaveWorkspace,
  loadWorkspaceMembers,
  transitionWorkspaceMember,
  transferWorkspaceOwnership,
  updateWorkspaceMemberRole,
} from "./workspace-members-api";

describe("workspace members API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("runtime-validates the bounded member projection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(workspaceMembers))),
    );

    const result = await loadWorkspaceMembers(workspaceMembers.workspaceId);

    expect(result).toEqual({ status: "success", members: workspaceMembers });
  });

  it("rejects malformed authority data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...workspaceMembers,
            items: [
              {
                ...workspaceMembers.items[0],
                capabilities: { canDisable: "yes" },
              },
            ],
          }),
        ),
      ),
    );

    const result = await loadWorkspaceMembers(workspaceMembers.workspaceId);

    expect(result.status).toBe("error");
  });

  it("sends CSRF and the member timestamp for role and lifecycle changes", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(workspaceMembers)),
    );
    vi.stubGlobal("fetch", fetchMock);
    const member = workspaceMembers.items[1]!;

    await updateWorkspaceMemberRole({
      csrfToken: "csrf",
      member,
      role: "viewer",
      workspaceId: workspaceMembers.workspaceId,
    });
    await transitionWorkspaceMember({
      action: "disable",
      csrfToken: "csrf",
      member,
      workspaceId: workspaceMembers.workspaceId,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `/api/v1/workspaces/${workspaceMembers.workspaceId}/members/${member.id}/role`,
      expect.objectContaining({
        body: JSON.stringify({
          role: "viewer",
          expectedUpdatedAt: member.updatedAt,
        }),
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf" }),
        method: "PUT",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `/api/v1/workspaces/${workspaceMembers.workspaceId}/members/${member.id}/disable`,
      expect.objectContaining({
        body: JSON.stringify({ expectedUpdatedAt: member.updatedAt }),
        method: "POST",
      }),
    );
  });

  it("sends both authority snapshots for transfer and leave", async () => {
    const member = workspaceMembers.items[1]!;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          members: workspaceMembers,
          navigationOutcome: { href: "/app/workspaces/current/settings" },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ navigationOutcome: { href: "/app/workspaces" } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await transferWorkspaceOwnership({
      csrfToken: "csrf",
      expectedWorkspaceUpdatedAt: "2026-08-03T08:30:00Z",
      member,
      workspaceId: workspaceMembers.workspaceId,
    });
    await leaveWorkspace({
      csrfToken: "csrf",
      currentWorkspaceId: workspaceMembers.workspaceId,
      member,
      workspaceId: workspaceMembers.workspaceId,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `/api/v1/workspaces/${workspaceMembers.workspaceId}/transfer-ownership`,
      expect.objectContaining({
        body: JSON.stringify({
          recipientMemberId: member.id,
          expectedWorkspaceUpdatedAt: "2026-08-03T08:30:00Z",
          expectedRecipientUpdatedAt: member.updatedAt,
        }),
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `/api/v1/workspaces/${workspaceMembers.workspaceId}/leave`,
      expect.objectContaining({
        body: JSON.stringify({
          expectedMemberUpdatedAt: member.updatedAt,
          expectedCurrentWorkspaceId: workspaceMembers.workspaceId,
        }),
        method: "POST",
      }),
    );
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
