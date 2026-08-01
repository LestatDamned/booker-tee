import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import {
  createProperty,
  type PropertyDirectoryDto,
} from "./api/properties-api";
import { PropertiesPage } from "./properties-page";

vi.mock("./api/properties-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/properties-api")>();
  return { ...actual, createProperty: vi.fn() };
});

describe("PropertiesPage", () => {
  beforeEach(() => {
    vi.mocked(createProperty).mockReset();
  });
  it("renders active properties with status counts and property-scoped reports", () => {
    renderPage(directory);

    expect(screen.getByRole("heading", { name: "Объекты" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Активные 1" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Архив 1" })).toBeVisible();
    expect(screen.getAllByText("Квартира")).toHaveLength(2);
    expect(screen.getAllByText("Активен")).toHaveLength(2);
    expect(screen.getAllByText("Красноярск, ул. Мира, 1")).toHaveLength(2);
    expect(
      screen.getAllByRole("link", {
        name: "Открыть отчёт по объекту «Квартира»",
      })[0],
    ).toHaveAttribute("href", `/reports?property_id=${directory.items[0]!.id}`);
  });

  it("shows archived objects from URL state", () => {
    renderPage(directory, "/properties?view=archived");

    expect(screen.getByRole("link", { name: "Архив 1" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getAllByText("Старый проект")).toHaveLength(2);
    expect(
      screen
        .getAllByText("Архив")
        .filter((label) => label.closest("[data-tone='neutral']")),
    ).toHaveLength(2);
    expect(screen.queryByText("Квартира")).not.toBeInTheDocument();
  });

  it("searches visible properties and offers one reset path", async () => {
    const user = userEvent.setup();
    renderPage(directory);

    await user.type(
      screen.getByRole("searchbox", {
        name: "Поиск по названию, короткому названию или адресу",
      }),
      "офис",
    );
    await user.click(screen.getByRole("button", { name: "Найти" }));

    expect(
      screen.getByRole("heading", { name: "По этому запросу объектов нет" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Очистить поиск" })).toBeVisible();
  });

  it("keeps a viewer readable without implying mutation authority", () => {
    renderPage({
      ...directory,
      capabilities: {
        canCreate: false,
        readonlyReasonCode: "financial_write_forbidden",
      },
      items: directory.items.map((property) => ({
        ...property,
        capabilities: {
          canUpdate: false,
          canArchive: false,
          canRestore: false,
        },
      })),
    });

    expect(
      screen.getByText("Объекты доступны только для просмотра"),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /Новый объект/ })).toBeNull();
  });

  it("focuses and explains an invalid required name", async () => {
    const user = userEvent.setup();
    renderPage(directory);

    await user.click(screen.getByRole("button", { name: "Новый объект" }));
    await user.click(screen.getByRole("button", { name: "Создать объект" }));

    expect(screen.getByText("Введите название объекта.")).toBeVisible();
    expect(screen.getByLabelText(/Название/)).toHaveFocus();
    expect(createProperty).not.toHaveBeenCalled();
  });

  it("protects a dirty draft and restores it after cancelling close", async () => {
    const user = userEvent.setup();
    renderPage(directory);

    await user.click(screen.getByRole("button", { name: "Новый объект" }));
    await user.type(screen.getByLabelText(/Название/), "Черновик");
    await user.click(screen.getByRole("button", { name: "Отмена" }));

    expect(
      screen.getByRole("dialog", { name: "Закрыть создание объекта?" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Продолжить создание" }),
    );
    expect(screen.getByLabelText(/Название/)).toHaveValue("Черновик");
  });

  it("keeps the draft and focuses a server-invalid field", async () => {
    const user = userEvent.setup();
    vi.mocked(createProperty).mockResolvedValue({
      status: "error",
      code: "validation_error",
      message: "Проверьте переданные данные.",
      fieldErrors: { shortName: ["Короткое имя уже не подходит."] },
    });
    renderPage(directory);

    await user.click(screen.getByRole("button", { name: "Новый объект" }));
    await user.type(screen.getByLabelText(/Название/), "Квартира");
    await user.type(screen.getByLabelText(/Короткое имя/), "Дом");
    await user.click(screen.getByRole("button", { name: "Создать объект" }));

    expect(
      await screen.findByText("Короткое имя уже не подходит."),
    ).toBeVisible();
    await waitFor(() =>
      expect(screen.getByLabelText(/Короткое имя/)).toHaveFocus(),
    );
    expect(screen.getByLabelText(/Название/)).toHaveValue("Квартира");
  });

  it("prevents repeated submit while creation is pending", async () => {
    const user = userEvent.setup();
    let resolveCreate!: (
      result: Awaited<ReturnType<typeof createProperty>>,
    ) => void;
    vi.mocked(createProperty).mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve;
      }),
    );
    renderPage(directory);

    await user.click(screen.getByRole("button", { name: "Новый объект" }));
    await user.type(screen.getByLabelText(/Название/), "Проект");
    const submit = screen.getByRole("button", { name: "Создать объект" });
    await user.click(submit);

    expect(screen.getByRole("button", { name: "Создаём…" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Создаём…" }));
    expect(createProperty).toHaveBeenCalledTimes(1);
    resolveCreate({
      status: "forbidden",
      message: "Создание объекта недоступно.",
    });
    expect(
      await screen.findByText("Создание объекта недоступно."),
    ).toBeVisible();
  });

  it("inserts only the committed property, closes and reports success", async () => {
    const user = userEvent.setup();
    const committed = {
      ...directory.items[0]!,
      id: "b994b9d8-eafb-45a0-b90c-b3cf31e1a13e",
      name: "Новый проект",
      shortName: "Проект",
      address: "Красноярск",
      updatedAt: "2026-08-01T10:00:00Z",
    };
    vi.mocked(createProperty).mockResolvedValue({
      status: "success",
      property: committed,
    });
    renderPage(directory);

    const trigger = screen.getByRole("button", { name: "Новый объект" });
    await user.click(trigger);
    await user.type(screen.getByLabelText(/Название/), "Новый проект");
    await user.type(screen.getByLabelText(/Короткое имя/), "Проект");
    await user.type(screen.getByLabelText(/Адрес/), "Красноярск");
    await user.click(screen.getByRole("button", { name: "Создать объект" }));

    await waitFor(() =>
      expect(screen.getByText("Объект «Новый проект» создан.")).toBeVisible(),
    );
    expect(screen.getAllByText("Новый проект")).toHaveLength(2);
    expect(createProperty).toHaveBeenCalledTimes(1);
    expect(createProperty).toHaveBeenCalledWith({
      csrfToken: "csrf-token",
      draft: {
        name: "Новый проект",
        shortName: "Проект",
        address: "Красноярск",
      },
    });
    expect(
      screen.queryByRole("dialog", { name: "Новый объект" }),
    ).not.toBeInTheDocument();
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});

function renderPage(
  currentDirectory: PropertyDirectoryDto,
  initialEntry = "/properties",
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <PropertiesPage directory={currentDirectory} session={session} />
    </MemoryRouter>,
  );
}

const directory: PropertyDirectoryDto = {
  items: [
    {
      id: "285c18d8-78bb-46d7-b6cd-d6fc897ab8a2",
      name: "Квартира",
      shortName: "Дом",
      address: "Красноярск, ул. Мира, 1",
      status: "active",
      archivedAt: null,
      updatedAt: "2026-08-01T08:30:00Z",
      capabilities: {
        canUpdate: true,
        canArchive: true,
        canRestore: false,
      },
    },
    {
      id: "1b7ba3c1-1af5-4dce-ab51-594adef47c48",
      name: "Старый проект",
      shortName: null,
      address: null,
      status: "archived",
      archivedAt: "2026-08-01T08:30:00Z",
      updatedAt: "2026-08-01T08:30:00Z",
      capabilities: {
        canUpdate: true,
        canArchive: false,
        canRestore: true,
      },
    },
  ],
  capabilities: { canCreate: true, readonlyReasonCode: null },
};

const session: SessionDto = {
  user: {
    id: "2290fe02-81cb-477e-a0e1-589783f8b316",
    email: "max@example.test",
    name: "Max",
  },
  workspace: {
    id: "53a112fc-8907-4692-8bf6-35128684b535",
    name: "Дом",
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
