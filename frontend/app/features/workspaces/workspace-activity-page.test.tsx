import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { session, workspaceActivity } from "./test-support";
import { WorkspaceActivityPage } from "./workspace-activity-page";

describe("WorkspaceActivityPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders URL-owned filters and the activity timeline", () => {
    renderPage(workspaceActivity);

    expect(
      screen.getByRole("heading", { name: "История действий" }),
    ).toBeVisible();
    expect(
      screen.getByText("Max изменил роль Анна: Наблюдатель → Редактор"),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Финансы" })).toHaveAttribute(
      "href",
      "/workspaces/c12c9ac8-6851-4467-b87a-da7fc70586c8/activity?scope=finance",
    );
    expect(screen.getByRole("link", { name: "Все" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("links only available entities with a canonical route", () => {
    const debtId = "b52c52d4-6d94-4a33-b5f1-0a0943a75727";
    renderPage({
      ...workspaceActivity,
      items: [
        {
          ...workspaceActivity.items[0]!,
          id: "ff99d62e-dd42-45f5-a7db-00faabfead75",
          eventType: "debt_updated",
          summaryCode: "debt_updated",
          scope: "finance",
          entity: {
            type: "debt",
            id: debtId,
            displayLabel: "Ипотека",
            isAvailable: true,
          },
          details: {
            ...workspaceActivity.items[0]!.details,
            displayLabel: "Ипотека",
          },
        },
        {
          ...workspaceActivity.items[0]!,
          id: "d30c767d-258b-4a10-99d8-ae9a86233936",
          eventType: "document_uploaded",
          summaryCode: "document_uploaded",
          scope: "finance",
          entity: {
            type: "uploaded_document",
            id: "86135df0-d55d-4e2d-9389-d029f5552c59",
            displayLabel: "statement.pdf",
            isAvailable: false,
          },
          details: {
            ...workspaceActivity.items[0]!.details,
            displayFilename: "statement.pdf",
          },
        },
        {
          ...workspaceActivity.items[0]!,
          id: "ed1873b7-e248-474a-b8c7-4d57647b8582",
          eventType: "manual_operation_updated",
          summaryCode: "manual_operation_updated",
          scope: "finance",
          entity: {
            type: "operation",
            id: "761bcb13-4891-444e-b026-f3ed295c3680",
            displayLabel: "Аренда",
            isAvailable: true,
          },
        },
      ],
    });

    expect(screen.getByRole("link", { name: "Ипотека" })).toHaveAttribute(
      "href",
      `/debts/${debtId}`,
    );
    expect(screen.getByText("statement.pdf · недоступно")).toBeVisible();
    expect(screen.queryByRole("link", { name: "statement.pdf" })).toBeNull();
    expect(
      screen.getByRole("link", { name: "Открыть операцию" }),
    ).toHaveAttribute(
      "href",
      "/operations?operation_id=761bcb13-4891-444e-b026-f3ed295c3680#operation-761bcb13-4891-444e-b026-f3ed295c3680",
    );
  });

  it("appends the next keyset page", async () => {
    const user = userEvent.setup();
    const initial = {
      ...workspaceActivity,
      nextCursor: {
        beforeCreatedAt: workspaceActivity.items[0]!.createdAt,
        beforeId: workspaceActivity.items[0]!.id,
        scope: "all" as const,
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
    renderPage(initial);

    await user.click(screen.getByRole("button", { name: "Показать ещё" }));

    expect(screen.getByText("Max восстановил пространство")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Показать ещё" })).toBeNull();
  });
});

function renderPage(activity = workspaceActivity) {
  return render(
    <MemoryRouter
      initialEntries={[
        `/workspaces/${activity.workspaceId}/activity?scope=all`,
      ]}
    >
      <WorkspaceActivityPage
        initialActivity={activity}
        scope="all"
        session={session}
      />
    </MemoryRouter>,
  );
}

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
