import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { workspaceActivity } from "./test-support";
import { WorkspaceActivitySection } from "./workspace-activity-section";

describe("WorkspaceActivitySection", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders server summary data and loads the next keyset page", async () => {
    const user = userEvent.setup();
    const initial = {
      ...workspaceActivity,
      nextCursor: {
        beforeCreatedAt: workspaceActivity.items[0]!.createdAt,
        beforeId: workspaceActivity.items[0]!.id,
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...workspaceActivity,
            items: [
              {
                ...workspaceActivity.items[0]!,
                id: "ff99d62e-dd42-45f5-a7db-00faabfead75",
                eventType: "workspace_restored",
                summaryCode: "workspace_restored",
              },
            ],
          }),
        ),
      ),
    );

    render(
      <WorkspaceActivitySection
        initialResult={{ status: "success", activity: initial }}
        workspaceId={workspaceActivity.workspaceId}
      />,
    );

    expect(
      screen.getByText("Max изменил роль Анна: Наблюдатель → Редактор"),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Показать ещё" }));
    expect(screen.getByText("Max восстановил пространство")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Показать ещё" })).toBeNull();
  });

  it("shows a non-blocking initial error", () => {
    render(
      <WorkspaceActivitySection
        initialResult={{ status: "error", message: "Backend недоступен." }}
        workspaceId={workspaceActivity.workspaceId}
      />,
    );

    expect(screen.getByText("Backend недоступен.")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Активность" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Повторить" })).toBeVisible();
  });

  it("reloads the first page after a committed administrative mutation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...workspaceActivity,
            items: [
              {
                ...workspaceActivity.items[0]!,
                eventType: "workspace_updated",
                summaryCode: "workspace_updated",
              },
            ],
          }),
        ),
      ),
    );
    const view = render(
      <WorkspaceActivitySection
        initialResult={{ status: "success", activity: workspaceActivity }}
        refreshToken={0}
        workspaceId={workspaceActivity.workspaceId}
      />,
    );

    view.rerender(
      <WorkspaceActivitySection
        initialResult={{ status: "success", activity: workspaceActivity }}
        refreshToken={1}
        workspaceId={workspaceActivity.workspaceId}
      />,
    );

    expect(
      await screen.findByText("Max изменил настройки пространства"),
    ).toBeVisible();
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
