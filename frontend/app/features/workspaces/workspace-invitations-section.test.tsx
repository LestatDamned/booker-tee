import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createWorkspaceInvitation,
  loadWorkspaceInvitations,
  revokeWorkspaceInvitation,
} from "./api/workspace-invitations-api";
import { workspaceInvitations } from "./test-support";
import { WorkspaceInvitationsSection } from "./workspace-invitations-section";

vi.mock("./api/workspace-invitations-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/workspace-invitations-api")>();
  return {
    ...actual,
    createWorkspaceInvitation: vi.fn(),
    loadWorkspaceInvitations: vi.fn(),
    revokeWorkspaceInvitation: vi.fn(),
  };
});

describe("WorkspaceInvitationsSection", () => {
  beforeEach(() => {
    vi.mocked(createWorkspaceInvitation).mockReset();
    vi.mocked(loadWorkspaceInvitations).mockReset();
    vi.mocked(revokeWorkspaceInvitation).mockReset();
  });

  it("shows a created credential only until it is dismissed", async () => {
    const user = userEvent.setup();
    vi.mocked(createWorkspaceInvitation).mockResolvedValue({
      status: "success",
      invitation: workspaceInvitations.items[0]!,
      invitations: workspaceInvitations,
      shareUrl: "https://example.test/app/workspaces/invitations/secret",
      replayed: false,
    });
    render(
      <WorkspaceInvitationsSection
        csrfToken="csrf"
        initialInvitations={workspaceInvitations}
      />,
    );

    await user.selectOptions(screen.getByLabelText("Роль"), "editor");
    await user.click(screen.getByRole("button", { name: "Создать ссылку" }));

    expect(createWorkspaceInvitation).toHaveBeenCalledWith({
      csrfToken: "csrf",
      idempotencyKey: expect.any(String),
      role: "editor",
      workspaceId: workspaceInvitations.workspaceId,
    });
    expect(screen.getByLabelText("Ссылка приглашения")).toHaveValue(
      "https://example.test/app/workspaces/invitations/secret",
    );

    await user.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(screen.queryByLabelText("Ссылка приглашения")).toBeNull();
  });

  it("requires confirmation before revoking", async () => {
    const user = userEvent.setup();
    vi.mocked(revokeWorkspaceInvitation).mockResolvedValue({
      status: "success",
      invitations: { ...workspaceInvitations, items: [] },
    });
    render(
      <WorkspaceInvitationsSection
        csrfToken="csrf"
        initialInvitations={workspaceInvitations}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Отозвать" }));
    expect(
      screen.getByRole("dialog", { name: "Отозвать приглашение?" }),
    ).toBeVisible();
    expect(revokeWorkspaceInvitation).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: "Отозвать приглашение" }),
    );
    expect(revokeWorkspaceInvitation).toHaveBeenCalledWith({
      csrfToken: "csrf",
      invitation: workspaceInvitations.items[0],
      workspaceId: workspaceInvitations.workspaceId,
    });
    expect(await screen.findByText("Ожидающих приглашений нет.")).toBeVisible();
  });
});
