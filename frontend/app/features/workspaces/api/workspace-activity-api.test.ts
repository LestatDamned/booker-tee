import { afterEach, describe, expect, it, vi } from "vitest";

import { workspaceActivity } from "../test-support";
import { loadWorkspaceActivity } from "./workspace-activity-api";

describe("loadWorkspaceActivity", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends the complete keyset cursor and parses the page", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(workspaceActivity)),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadWorkspaceActivity(workspaceActivity.workspaceId, {
      beforeCreatedAt: "2026-08-03T08:30:00Z",
      beforeId: "d37da8b5-6a8e-4e51-bcea-e97822bf5212",
      scope: "finance",
    });

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/workspaces/${workspaceActivity.workspaceId}/activity?scope=finance&beforeCreatedAt=2026-08-03T08%3A30%3A00Z&beforeId=d37da8b5-6a8e-4e51-bcea-e97822bf5212`,
      expect.anything(),
    );
  });

  it("keeps forbidden activity non-fatal for workspace settings", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 403 }))),
    );

    await expect(
      loadWorkspaceActivity(workspaceActivity.workspaceId),
    ).resolves.toEqual({
      status: "forbidden",
      message: "Активность workspace недоступна.",
    });
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
