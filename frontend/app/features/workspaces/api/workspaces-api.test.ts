import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createSuccessPayload,
  selectSuccessPayload,
  workspaceDirectory,
} from "../test-support";
import {
  createWorkspace,
  loadWorkspaces,
  selectWorkspace,
} from "./workspaces-api";

describe("Workspaces API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("validates the directory at the network boundary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(workspaceDirectory))),
    );

    await expect(loadWorkspaces()).resolves.toEqual({
      status: "success",
      directory: workspaceDirectory,
    });
  });

  it("rejects client-invented capabilities", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...workspaceDirectory,
            items: [
              {
                ...workspaceDirectory.items[0],
                capabilities: { canSelect: true },
              },
            ],
          }),
        ),
      ),
    );

    await expect(loadWorkspaces()).resolves.toEqual({
      status: "error",
      message: "API вернул пространства неожиданного формата.",
    });
  });

  it("creates with CSRF and a stable idempotency key", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(createSuccessPayload, 201)),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await createWorkspace({
      csrfToken: "csrf-token",
      idempotencyKey: "5ad34d42-50d6-453c-aeb9-0f4fb3b26d15",
      draft: {
        name: "Новый проект",
        workspaceType: "project",
        defaultCurrency: "RUB",
      },
    });

    expect(result).toEqual({
      status: "success",
      href: "/app/workspaces",
      workspace: createSuccessPayload.workspace,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/workspaces",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Idempotency-Key": "5ad34d42-50d6-453c-aeb9-0f4fb3b26d15",
          "X-CSRF-Token": "csrf-token",
        }),
      }),
    );
  });

  it("preserves create field errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: "workspace_validation_error",
                message: "Проверьте переданные данные.",
                fieldErrors: { name: ["Название обязательно."] },
              },
            },
            422,
          ),
        ),
      ),
    );

    await expect(
      createWorkspace({
        csrfToken: "csrf-token",
        idempotencyKey: crypto.randomUUID(),
        draft: {
          name: "",
          workspaceType: "personal",
          defaultCurrency: "RUB",
        },
      }),
    ).resolves.toMatchObject({
      status: "error",
      code: "workspace_validation_error",
      fieldErrors: { name: ["Название обязательно."] },
    });
  });

  it("switches with CSRF and expected current identity", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(selectSuccessPayload)),
    );
    vi.stubGlobal("fetch", fetchMock);
    const target = workspaceDirectory.items[1]!;

    await expect(
      selectWorkspace({
        csrfToken: "csrf-token",
        currentWorkspaceId: workspaceDirectory.currentWorkspaceId,
        workspaceId: target.id,
      }),
    ).resolves.toEqual({ status: "success", href: "/app/workspaces" });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/workspaces/${target.id}/select`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expectedCurrentWorkspaceId: workspaceDirectory.currentWorkspaceId,
        }),
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
      }),
    );
  });

  it("keeps switch conflicts recoverable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: "workspace_switch_conflict",
                message: "Контекст уже изменился.",
              },
            },
            409,
          ),
        ),
      ),
    );

    await expect(
      selectWorkspace({
        csrfToken: "csrf-token",
        currentWorkspaceId: workspaceDirectory.currentWorkspaceId,
        workspaceId: workspaceDirectory.items[1]!.id,
      }),
    ).resolves.toEqual({
      status: "conflict",
      message: "Контекст уже изменился.",
    });
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
