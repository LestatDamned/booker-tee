import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import * as invitationApi from "./api/workspace-invitations-api";
import { WorkspaceInvitationPage } from "./workspace-invitation-page";

const invitation = {
  workspaceName: "Семейный бюджет",
  role: "viewer" as const,
  expiresAt: "2026-08-08T12:00:00Z",
};

describe("Workspace invitation page", () => {
  afterEach(() => vi.restoreAllMocks());

  it("preserves the invitation destination for login and signup", () => {
    render(
      <WorkspaceInvitationPage
        invitation={invitation}
        invitationToken="private-token"
        session={null}
      />,
    );

    expect(screen.getByText("Семейный бюджет")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/app/auth/login?next=%2Fapp%2Fworkspaces%2Finvitations%2Fprivate-token",
    );
    expect(
      screen.getByRole("link", { name: "Создать аккаунт" }),
    ).toHaveAttribute(
      "href",
      "/app/auth/signup?next=%2Fapp%2Fworkspaces%2Finvitations%2Fprivate-token",
    );
  });

  it("accepts with CSRF and performs the server-owned hard navigation", async () => {
    const navigate = vi.fn();
    const accept = vi
      .spyOn(invitationApi, "acceptPublicWorkspaceInvitation")
      .mockResolvedValue({ status: "success", href: "/app/workspaces" });
    render(
      <WorkspaceInvitationPage
        invitation={invitation}
        invitationToken="private-token"
        navigate={navigate}
        session={session}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Принять приглашение" }),
    );

    expect(accept).toHaveBeenCalledWith({
      csrfToken: "csrf-token",
      invitationToken: "private-token",
    });
    expect(navigate).toHaveBeenCalledWith("/app/workspaces");
  });
});

const session: SessionDto = {
  user: {
    id: "11111111-1111-1111-1111-111111111111",
    email: "member@example.test",
    name: "Member",
  },
  workspace: {
    id: "22222222-2222-2222-2222-222222222222",
    name: "Личное",
    type: "personal",
    defaultCurrency: "RUB",
  },
  membership: { role: "owner", status: "active" },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canManageMembers: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};
