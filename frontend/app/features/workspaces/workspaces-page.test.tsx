import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { loadSession } from "../../api/session";
import { createWorkspace, selectWorkspace } from "./api/workspaces-api";
import { session, workspaceDirectory } from "./test-support";
import { WorkspacesPage } from "./workspaces-page";

vi.mock("./api/workspaces-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/workspaces-api")>();
  return {
    ...actual,
    createWorkspace: vi.fn(),
    selectWorkspace: vi.fn(),
  };
});

vi.mock("../../api/session", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/session")>();
  return { ...actual, loadSession: vi.fn() };
});

describe("WorkspacesPage", () => {
  beforeEach(() => {
    vi.mocked(createWorkspace).mockReset();
    vi.mocked(selectWorkspace).mockReset();
    vi.mocked(loadSession).mockReset();
    window.sessionStorage.clear();
  });

  it("shows current, selectable and inactive records without clickable rows", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: "Рабочие пространства" }),
    ).toHaveFocus();
    expect(screen.getAllByText("Дом")).toHaveLength(5);
    expect(screen.getAllByText("Текущее")).toHaveLength(2);
    expect(screen.getAllByText("Активно")).toHaveLength(2);
    expect(screen.getAllByText("Неактивно")).toHaveLength(2);
    expect(
      screen.getAllByRole("button", {
        name: "Выбрать пространство «Семейный бюджет»",
      }),
    ).toHaveLength(2);
    expect(
      screen.queryByRole("button", { name: "Выбрать пространство «Дом»" }),
    ).toBeNull();
    expect(screen.queryByRole("link", { name: "Семейный бюджет" })).toBeNull();
  });

  it("focuses an invalid name and protects a dirty draft", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      screen.getByRole("button", { name: "Новое пространство" }),
    );
    await user.click(screen.getByRole("button", { name: "Создать и перейти" }));
    expect(screen.getByText("Введите название пространства.")).toBeVisible();
    expect(screen.getByLabelText(/Название/)).toHaveFocus();
    expect(createWorkspace).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText(/Название/), "Черновик");
    await user.click(screen.getByRole("button", { name: "Отмена" }));
    expect(
      screen.getByRole("dialog", {
        name: "Закрыть создание пространства?",
      }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Продолжить создание" }),
    );
    expect(screen.getByLabelText(/Название/)).toHaveValue("Черновик");
  });

  it("creates with server options and performs a hard boundary navigation", async () => {
    const user = userEvent.setup();
    const boundaryNavigate = vi.fn();
    vi.mocked(createWorkspace).mockResolvedValue({
      status: "success",
      href: "/app/workspaces",
      workspace: {
        ...workspaceDirectory.items[1]!,
        name: "Новый проект",
        type: "project",
      },
    });
    renderPage(boundaryNavigate);

    await user.click(
      screen.getByRole("button", { name: "Новое пространство" }),
    );
    await user.type(screen.getByLabelText(/Название/), "Новый проект");
    await user.selectOptions(screen.getByLabelText(/Тип/), "project");
    await user.click(screen.getByRole("button", { name: "Создать и перейти" }));

    expect(createWorkspace).toHaveBeenCalledWith(
      expect.objectContaining({
        csrfToken: "csrf-token",
        draft: {
          name: "Новый проект",
          workspaceType: "project",
          defaultCurrency: "RUB",
        },
        idempotencyKey: expect.any(String),
      }),
    );
    expect(boundaryNavigate).toHaveBeenCalledWith(
      "/app/workspaces",
      "Пространство «Новый проект» создано и выбрано.",
    );
  });

  it("switches only after a committed response", async () => {
    const user = userEvent.setup();
    const boundaryNavigate = vi.fn();
    let resolveSwitch!: (
      value: Awaited<ReturnType<typeof selectWorkspace>>,
    ) => void;
    vi.mocked(selectWorkspace).mockReturnValue(
      new Promise((resolve) => {
        resolveSwitch = resolve;
      }),
    );
    renderPage(boundaryNavigate);

    const actions = screen.getAllByRole("button", {
      name: "Выбрать пространство «Семейный бюджет»",
    });
    await user.click(actions[0]!);
    expect(screen.getAllByText("Переключаем…")).toHaveLength(2);
    expect(boundaryNavigate).not.toHaveBeenCalled();

    resolveSwitch({ status: "success", href: "/app/workspaces" });
    await waitFor(() =>
      expect(boundaryNavigate).toHaveBeenCalledWith(
        "/app/workspaces",
        "Текущее пространство: «Семейный бюджет».",
      ),
    );
    expect(selectWorkspace).toHaveBeenCalledWith({
      csrfToken: "csrf-token",
      currentWorkspaceId: workspaceDirectory.currentWorkspaceId,
      workspaceId: workspaceDirectory.items[1]!.id,
    });
  });

  it("shows stale switch recovery without changing the current marker", async () => {
    const user = userEvent.setup();
    const boundaryNavigate = vi.fn();
    vi.mocked(selectWorkspace).mockResolvedValue({
      status: "conflict",
      message: "Контекст уже изменился в другой вкладке.",
    });
    renderPage(boundaryNavigate);

    await user.click(
      screen.getAllByRole("button", {
        name: "Выбрать пространство «Семейный бюджет»",
      })[0]!,
    );

    expect(
      await screen.findByText("Контекст изменился в другой вкладке"),
    ).toBeVisible();
    expect(screen.getAllByText("Текущее")).toHaveLength(2);
    expect(boundaryNavigate).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Обновить" }));
    expect(boundaryNavigate).toHaveBeenCalledWith("/app/workspaces");
  });

  it("checks session truth after an ambiguous switch timeout", async () => {
    const user = userEvent.setup();
    const boundaryNavigate = vi.fn();
    vi.mocked(selectWorkspace).mockResolvedValue({
      status: "error",
      code: "network_error",
      message: "Backend недоступен.",
      fieldErrors: {},
    });
    vi.mocked(loadSession).mockResolvedValue({
      status: "authenticated",
      session: {
        ...session,
        workspace: {
          ...session.workspace,
          id: workspaceDirectory.items[1]!.id,
        },
      },
    });
    renderPage(boundaryNavigate);

    await user.click(
      screen.getAllByRole("button", {
        name: "Выбрать пространство «Семейный бюджет»",
      })[0]!,
    );

    await waitFor(() =>
      expect(boundaryNavigate).toHaveBeenCalledWith("/app/workspaces"),
    );
    expect(loadSession).toHaveBeenCalledOnce();
  });

  it("renders an explicit empty recovery without duplicating the create action", () => {
    renderPage(vi.fn(), { ...workspaceDirectory, items: [] });

    expect(screen.getByText("Нет доступных пространств")).toBeVisible();
    expect(
      screen.getAllByRole("button", { name: "Новое пространство" }),
    ).toHaveLength(1);
  });
});

function renderPage(
  boundaryNavigate = vi.fn(),
  directory = workspaceDirectory,
) {
  return render(
    <MemoryRouter initialEntries={["/workspaces"]}>
      <WorkspacesPage
        boundaryNavigate={boundaryNavigate}
        directory={directory}
        session={session}
      />
    </MemoryRouter>,
  );
}
