import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  loadWorkspaceSettings,
  updateWorkspaceSettings,
} from "./api/workspace-settings-api";
import { session, workspaceSettings } from "./test-support";
import { WorkspaceSettingsPage } from "./workspace-settings-page";

vi.mock("./api/workspace-settings-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/workspace-settings-api")>();
  return {
    ...actual,
    loadWorkspaceSettings: vi.fn(),
    updateWorkspaceSettings: vi.fn(),
  };
});

describe("WorkspaceSettingsPage", () => {
  beforeEach(() => {
    vi.mocked(loadWorkspaceSettings).mockReset();
    vi.mocked(updateWorkspaceSettings).mockReset();
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
    expect(screen.getByText("Наблюдатель", { exact: false })).toBeVisible();
  });
});

function renderPage(settings = workspaceSettings) {
  return render(
    <MemoryRouter
      initialEntries={[`/workspaces/${settings.workspace.id}/settings`]}
    >
      <WorkspaceSettingsPage initialSettings={settings} session={session} />
    </MemoryRouter>,
  );
}
