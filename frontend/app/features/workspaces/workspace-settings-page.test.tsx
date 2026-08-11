import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  loadWorkspaceSettings,
  transitionWorkspaceLifecycle,
  updateWorkspaceSettings,
} from "./api/workspace-settings-api";
import {
  leaveWorkspace,
  transitionWorkspaceMember,
  transferWorkspaceOwnership,
  updateWorkspaceMemberRole,
} from "./api/workspace-members-api";
import {
  session,
  workspaceInvitations,
  workspaceMembers,
  workspaceSettings,
} from "./test-support";
import { WorkspaceSettingsPage } from "./workspace-settings-page";

vi.mock("./api/workspace-settings-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/workspace-settings-api")>();
  return {
    ...actual,
    loadWorkspaceSettings: vi.fn(),
    transitionWorkspaceLifecycle: vi.fn(),
    updateWorkspaceSettings: vi.fn(),
  };
});

vi.mock("./api/workspace-members-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/workspace-members-api")>();
  return {
    ...actual,
    leaveWorkspace: vi.fn(),
    transitionWorkspaceMember: vi.fn(),
    transferWorkspaceOwnership: vi.fn(),
    updateWorkspaceMemberRole: vi.fn(),
  };
});

describe("WorkspaceSettingsPage", () => {
  beforeEach(() => {
    vi.mocked(loadWorkspaceSettings).mockReset();
    vi.mocked(transitionWorkspaceLifecycle).mockReset();
    vi.mocked(updateWorkspaceSettings).mockReset();
    vi.mocked(transitionWorkspaceMember).mockReset();
    vi.mocked(transferWorkspaceOwnership).mockReset();
    vi.mocked(leaveWorkspace).mockReset();
    vi.mocked(updateWorkspaceMemberRole).mockReset();
  });

  it("renders owner form and truthful lifecycle impact", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Дом" })).toBeVisible();
    expect(screen.getByLabelText(/Название/)).toHaveValue("Дом");
    expect(
      screen.getByText("Ранее сохранённые данные не изменятся"),
    ).toBeVisible();
    expect(screen.getByText("Активные сессии")).toBeVisible();
    expect(screen.getAllByText("2", { selector: "dd" })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Сохранить" })).toBeDisabled();
    expect(
      screen.getByRole("link", { name: "История действий" }),
    ).toHaveAttribute(
      "href",
      `/workspaces/${workspaceSettings.workspace.id}/activity`,
    );
  });

  it("validates, saves and replaces the committed snapshot", async () => {
    const user = userEvent.setup();
    vi.mocked(updateWorkspaceSettings).mockResolvedValue({
      status: "success",
      settings: {
        ...workspaceSettings,
        workspace: {
          ...workspaceSettings.workspace,
          name: "Семейный дом",
          type: "family",
          defaultCurrency: "USD",
          updatedAt: "2026-08-03T10:00:00Z",
        },
      },
    });
    renderPage();

    await user.clear(screen.getByLabelText(/Название/));
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(screen.getByText("Введите название пространства.")).toBeVisible();
    expect(screen.getByLabelText(/Название/)).toHaveFocus();
    expect(updateWorkspaceSettings).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText(/Название/), "Семейный дом");
    await user.selectOptions(screen.getByLabelText(/Тип/), "family");
    await user.selectOptions(screen.getByLabelText(/Основная валюта/), "USD");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(updateWorkspaceSettings).toHaveBeenCalledWith({
      csrfToken: "csrf-token",
      draft: {
        name: "Семейный дом",
        workspaceType: "family",
        defaultCurrency: "USD",
      },
      expectedUpdatedAt: workspaceSettings.workspace.updatedAt,
      workspaceId: workspaceSettings.workspace.id,
    });
    expect(
      await screen.findByText("Настройки пространства сохранены."),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Сохранить" })).toBeDisabled();
  });

  it("replaces the short form with current values after a stale conflict", async () => {
    const user = userEvent.setup();
    vi.mocked(updateWorkspaceSettings).mockResolvedValue({
      status: "conflict",
      message: "Workspace уже изменён.",
    });
    vi.mocked(loadWorkspaceSettings).mockResolvedValue({
      status: "success",
      settings: {
        ...workspaceSettings,
        workspace: {
          ...workspaceSettings.workspace,
          name: "Имя из другой вкладки",
          updatedAt: "2026-08-03T10:10:00Z",
        },
      },
    });
    renderPage();

    await user.clear(screen.getByLabelText(/Название/));
    await user.type(screen.getByLabelText(/Название/), "Мой черновик");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(
      await screen.findByText("Настройки изменились в другой вкладке"),
    ).toBeVisible();
    await waitFor(() =>
      expect(screen.getByLabelText(/Название/)).toHaveValue(
        "Имя из другой вкладки",
      ),
    );
    expect(loadWorkspaceSettings).toHaveBeenCalledWith(
      workspaceSettings.workspace.id,
    );
    expect(
      screen.getByRole("heading", { name: "Имя из другой вкладки" }),
    ).toBeVisible();
    expect(screen.getByText(/Повторите нужное изменение/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Сохранить" })).toBeDisabled();
  });

  it("offers a retry when the authoritative reload after conflict fails", async () => {
    const user = userEvent.setup();
    vi.mocked(updateWorkspaceSettings).mockResolvedValue({
      status: "conflict",
      message: "Workspace уже изменён.",
    });
    vi.mocked(loadWorkspaceSettings)
      .mockResolvedValueOnce({
        status: "error",
        message: "Backend недоступен.",
      })
      .mockResolvedValueOnce({
        status: "success",
        settings: {
          ...workspaceSettings,
          workspace: {
            ...workspaceSettings.workspace,
            name: "Актуальное имя",
            updatedAt: "2026-08-03T10:10:00Z",
          },
        },
      });
    renderPage();

    await user.clear(screen.getByLabelText(/Название/));
    await user.type(screen.getByLabelText(/Название/), "Устаревшее имя");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(
      await screen.findByText("Не удалось загрузить актуальные настройки"),
    ).toBeVisible();
    expect(screen.getByText("Backend недоступен.")).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Повторить загрузку" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Актуальное имя" }),
    ).toBeVisible();
    expect(screen.getByLabelText(/Название/)).toHaveValue("Актуальное имя");
    expect(loadWorkspaceSettings).toHaveBeenCalledTimes(2);
  });

  it("renders a semantic read-only projection for a non-owner", () => {
    renderPage({
      ...workspaceSettings,
      workspace: {
        ...workspaceSettings.workspace,
        membership: {
          ...workspaceSettings.workspace.membership,
          role: "viewer",
        },
        capabilities: {
          ...workspaceSettings.workspace.capabilities,
          canUpdate: false,
          canManageMembers: false,
          canInvite: false,
        },
      },
      lifecycleImpact: null,
    });

    expect(screen.queryByLabelText(/Название/)).toBeNull();
    expect(screen.getByText("Только чтение")).toBeVisible();
    expect(screen.getByText("Доступно только владельцу")).toBeVisible();
    expect(
      screen.getAllByText("Наблюдатель", { exact: false })[0],
    ).toBeVisible();
  });

  it("uses server capabilities for inline role changes", async () => {
    const user = userEvent.setup();
    vi.mocked(updateWorkspaceMemberRole).mockResolvedValue({
      status: "success",
      members: {
        ...workspaceMembers,
        items: workspaceMembers.items.map((member) =>
          member.name === "Анна" ? { ...member, role: "viewer" } : member,
        ),
      },
    });
    renderPage();

    await user.selectOptions(screen.getByLabelText("Роль: Анна"), "viewer");

    expect(updateWorkspaceMemberRole).toHaveBeenCalledWith({
      csrfToken: "csrf-token",
      member: workspaceMembers.items[1],
      role: "viewer",
      workspaceId: workspaceMembers.workspaceId,
    });
    await waitFor(() =>
      expect(screen.getByLabelText("Роль: Анна")).toHaveValue("viewer"),
    );
  });

  it("requires confirmation before disabling access", async () => {
    const user = userEvent.setup();
    vi.mocked(transitionWorkspaceMember).mockResolvedValue({
      status: "success",
      members: {
        ...workspaceMembers,
        items: workspaceMembers.items.map((member) =>
          member.name === "Анна"
            ? {
                ...member,
                status: "disabled",
                capabilities: {
                  ...member.capabilities,
                  canDisable: false,
                  canReactivate: true,
                },
              }
            : member,
        ),
      },
    });
    renderPage();

    await user.click(screen.getByRole("button", { name: "Отключить" }));
    expect(
      screen.getByRole("dialog", { name: "Отключить участника?" }),
    ).toBeVisible();
    expect(transitionWorkspaceMember).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Отмена" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Отключить" })).toHaveFocus(),
    );
    await user.click(screen.getByRole("button", { name: "Отключить" }));

    await user.click(screen.getByRole("button", { name: "Отключить доступ" }));
    expect(transitionWorkspaceMember).toHaveBeenCalledWith({
      action: "disable",
      csrfToken: "csrf-token",
      member: workspaceMembers.items[1],
      workspaceId: workspaceMembers.workspaceId,
    });
    expect(await screen.findByText("Отключён")).toBeVisible();
  });

  it("requires confirmation and a hard boundary reload for ownership transfer", async () => {
    const user = userEvent.setup();
    const boundaryNavigate = vi.fn();
    vi.mocked(transferWorkspaceOwnership).mockResolvedValue({
      status: "success",
      href: `/app/workspaces/${workspaceSettings.workspace.id}/settings`,
      members: workspaceMembers,
    });
    renderPage(workspaceSettings, boundaryNavigate);

    await user.click(
      screen.getByRole("button", { name: "Передать владение участнику Анна" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Передать владение?" }),
    ).toBeVisible();
    expect(transferWorkspaceOwnership).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Передать владение" }));

    expect(transferWorkspaceOwnership).toHaveBeenCalledWith({
      csrfToken: session.csrfToken,
      expectedWorkspaceUpdatedAt: workspaceSettings.workspace.updatedAt,
      member: workspaceMembers.items[1],
      workspaceId: workspaceMembers.workspaceId,
    });
    expect(boundaryNavigate).toHaveBeenCalledWith(
      `/app/workspaces/${workspaceSettings.workspace.id}/settings`,
      "Владение пространством передано: Анна.",
    );
  });

  it("requires confirmation and reloads the fallback after self-leave", async () => {
    const user = userEvent.setup();
    const boundaryNavigate = vi.fn();
    const leavingMembers: typeof workspaceMembers = {
      ...workspaceMembers,
      items: workspaceMembers.items.map((member) =>
        member.isSelf
          ? {
              ...member,
              role: "admin",
              capabilities: { ...member.capabilities, canLeave: true },
              blockingReasonCodes: [],
            }
          : {
              ...member,
              capabilities: {
                ...member.capabilities,
                canTransferOwnership: false,
              },
            },
      ),
    };
    vi.mocked(leaveWorkspace).mockResolvedValue({
      status: "success",
      href: "/app/workspaces",
    });
    renderPage(workspaceSettings, boundaryNavigate, leavingMembers);

    await user.click(screen.getByRole("button", { name: "Выйти" }));
    expect(
      screen.getByRole("dialog", { name: "Выйти из пространства?" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Выйти из пространства" }),
    );

    expect(leaveWorkspace).toHaveBeenCalledWith({
      csrfToken: session.csrfToken,
      currentWorkspaceId: session.workspace.id,
      member: leavingMembers.items[0],
      workspaceId: leavingMembers.workspaceId,
    });
    expect(boundaryNavigate).toHaveBeenCalledWith(
      "/app/workspaces",
      "Вы вышли из рабочего пространства.",
    );
  });

  it("explains deactivation and crosses a hard workspace boundary", async () => {
    const user = userEvent.setup();
    const boundaryNavigate = vi.fn();
    vi.mocked(transitionWorkspaceLifecycle).mockResolvedValue({
      status: "success",
      href: "/app/workspaces",
    });
    renderPage(workspaceSettings, boundaryNavigate);

    await user.click(screen.getByRole("button", { name: "Деактивировать" }));
    expect(
      screen.getByRole("dialog", { name: "Деактивировать пространство?" }),
    ).toBeVisible();
    expect(screen.getByText(/Приглашения будут отозваны/)).toBeVisible();
    expect(transitionWorkspaceLifecycle).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: "Да, деактивировать" }),
    );

    expect(transitionWorkspaceLifecycle).toHaveBeenCalledWith({
      action: "deactivate",
      csrfToken: session.csrfToken,
      expectedCurrentWorkspaceId: session.workspace.id,
      expectedWorkspaceUpdatedAt: workspaceSettings.workspace.updatedAt,
      workspaceId: workspaceSettings.workspace.id,
    });
    expect(boundaryNavigate).toHaveBeenCalledWith(
      "/app/workspaces",
      "Рабочее пространство деактивировано.",
    );
  });

  it("restores without promising to resurrect invitations or integrations", async () => {
    const user = userEvent.setup();
    const boundaryNavigate = vi.fn();
    const inactiveSettings = {
      ...workspaceSettings,
      workspace: {
        ...workspaceSettings.workspace,
        isActive: false,
        archivedAt: workspaceSettings.workspace.updatedAt,
        capabilities: {
          ...workspaceSettings.workspace.capabilities,
          canUpdate: false,
          canDeactivate: false,
          canRestore: true,
        },
        blockingReasonCodes: ["workspace_inactive" as const],
      },
    };
    vi.mocked(transitionWorkspaceLifecycle).mockResolvedValue({
      status: "success",
      href: "/app/workspaces",
    });
    renderPage(inactiveSettings, boundaryNavigate);

    await user.click(screen.getByRole("button", { name: "Восстановить" }));
    expect(screen.getByText(/останутся отключёнными/)).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Восстановить пространство" }),
    );

    expect(transitionWorkspaceLifecycle).toHaveBeenCalledWith(
      expect.objectContaining({ action: "restore" }),
    );
    expect(boundaryNavigate).toHaveBeenCalledWith(
      "/app/workspaces",
      "Рабочее пространство восстановлено.",
    );
  });

  it("shows the server fallback gate instead of a destructive control", () => {
    renderPage({
      ...workspaceSettings,
      workspace: {
        ...workspaceSettings.workspace,
        capabilities: {
          ...workspaceSettings.workspace.capabilities,
          canDeactivate: false,
        },
        blockingReasonCodes: ["workspace_fallback_required"],
      },
    });

    expect(
      screen.getByText("Нужно другое активное пространство"),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Деактивировать" })).toBeNull();
  });
});

function renderPage(
  settings = workspaceSettings,
  boundaryNavigate = vi.fn(),
  members = workspaceMembers,
) {
  return render(
    <MemoryRouter
      initialEntries={[`/workspaces/${settings.workspace.id}/settings`]}
    >
      <WorkspaceSettingsPage
        boundaryNavigate={boundaryNavigate}
        initialInvitations={workspaceInvitations}
        initialMembers={members}
        initialSettings={settings}
        session={session}
      />
    </MemoryRouter>,
  );
}
