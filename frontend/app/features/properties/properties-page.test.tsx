import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import {
  changePropertyLifecycle,
  createProperty,
  loadProperties,
  type PropertyDirectoryDto,
  updateProperty,
} from "./api/properties-api";
import { PropertiesPage } from "./properties-page";

vi.mock("./api/properties-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/properties-api")>();
  return {
    ...actual,
    changePropertyLifecycle: vi.fn(),
    createProperty: vi.fn(),
    loadProperties: vi.fn(),
    updateProperty: vi.fn(),
  };
});

describe("PropertiesPage", () => {
  beforeEach(() => {
    vi.mocked(changePropertyLifecycle).mockReset();
    vi.mocked(createProperty).mockReset();
    vi.mocked(loadProperties).mockReset();
    vi.mocked(updateProperty).mockReset();
  });
  it("keeps one direct row action and puts property reports in compact overflow", async () => {
    const user = userEvent.setup();
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
    expect(screen.getAllByRole("button", { name: "Изменить" })).toHaveLength(2);
    const actionMenus = screen.getAllByRole("button", {
      name: "Ещё действия",
    });
    expect(actionMenus).toHaveLength(2);
    expect(
      screen.queryByRole("link", {
        name: "Открыть отчёт по объекту «Квартира»",
      }),
    ).toBeNull();

    await user.click(actionMenus[0]!);
    expect(
      screen.getByRole("link", {
        name: "Открыть отчёт по объекту «Квартира»",
      }),
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
    expect(screen.queryByRole("button", { name: "Изменить" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Ещё действия" })).toBeNull();
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

  it("opens one row editor with linked disclosure and field focus", async () => {
    const user = userEvent.setup();
    renderPage(directory);
    const property = directory.items[0]!;
    const trigger = editButton(property.id);

    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(trigger).toHaveAttribute(
      "aria-controls",
      `property-edit-desktop-${property.id}`,
    );
    expect(
      screen.getAllByRole("heading", { name: "Изменить объект" }),
    ).toHaveLength(2);
    await waitFor(() => expect(editField(property.id, "name")).toHaveFocus());
    expect(editField(property.id, "name")).toHaveValue("Квартира");
  });

  it("keeps an invalid edit draft local and focuses the first field", async () => {
    const user = userEvent.setup();
    const property = directory.items[0]!;
    renderPage(directory);

    await user.click(editButton(property.id));
    await user.clear(editField(property.id, "name"));
    await user.click(screen.getAllByRole("button", { name: "Сохранить" })[0]!);

    expect(
      await screen.findAllByText("Введите название объекта."),
    ).toHaveLength(2);
    expect(updateProperty).not.toHaveBeenCalled();
    await waitFor(() => expect(editField(property.id, "name")).toHaveFocus());
  });

  it("requires confirmation before switching a dirty row editor", async () => {
    const user = userEvent.setup();
    const twoActive: PropertyDirectoryDto = {
      ...directory,
      items: directory.items.map((property) => ({
        ...property,
        status: "active",
        archivedAt: null,
        capabilities: {
          canUpdate: true,
          canArchive: true,
          canRestore: false,
        },
      })),
    };
    renderPage(twoActive);
    const first = directory.items[0]!;
    const second = directory.items[1]!;

    await user.click(editButton(first.id));
    await user.clear(editField(first.id, "name"));
    await user.type(editField(first.id, "name"), "Черновик");
    await user.click(editButton(second.id));

    expect(
      screen.getByRole("dialog", { name: "Перейти к другому объекту?" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Продолжить редактирование" }),
    );
    expect(editField(first.id, "name")).toHaveValue("Черновик");

    await user.click(editButton(second.id));
    await user.click(
      screen.getByRole("button", { name: "Отменить изменения" }),
    );
    await waitFor(() => expect(editField(second.id, "name")).toHaveFocus());
    expect(editField(second.id, "name")).toHaveValue("Старый проект");
  });

  it("preserves a conflict draft until explicit authoritative reload", async () => {
    const user = userEvent.setup();
    const property = directory.items[0]!;
    vi.mocked(updateProperty).mockResolvedValue({
      status: "conflict",
      message: "Объект уже изменился. Загрузите актуальные данные.",
    });
    vi.mocked(loadProperties).mockResolvedValue({
      status: "success",
      directory: {
        ...directory,
        items: [
          {
            ...property,
            name: "Актуальное имя",
            updatedAt: "2026-08-01T09:00:00Z",
          },
          directory.items[1]!,
        ],
      },
    });
    renderPage(directory);

    await user.click(editButton(property.id));
    await user.clear(editField(property.id, "name"));
    await user.type(editField(property.id, "name"), "Мой draft");
    await user.click(screen.getAllByRole("button", { name: "Сохранить" })[0]!);

    expect(await screen.findAllByText("Объект уже был изменён")).toHaveLength(
      2,
    );
    expect(editField(property.id, "name")).toHaveValue("Мой draft");
    await user.click(
      screen.getAllByRole("button", { name: "Обновить данные" })[0]!,
    );
    await waitFor(() =>
      expect(editField(property.id, "name")).toHaveValue("Актуальное имя"),
    );
  });

  it("replaces only the committed row and sends its optimistic token", async () => {
    const user = userEvent.setup();
    const property = directory.items[0]!;
    const committed = {
      ...property,
      name: "Квартира после ремонта",
      updatedAt: "2026-08-01T09:00:00Z",
    };
    vi.mocked(updateProperty).mockResolvedValue({
      status: "success",
      property: committed,
    });
    renderPage(directory);

    const trigger = editButton(property.id);
    await user.click(trigger);
    await user.clear(editField(property.id, "name"));
    await user.type(editField(property.id, "name"), committed.name);
    await user.click(screen.getAllByRole("button", { name: "Сохранить" })[0]!);

    expect(
      await screen.findByText(`Объект «${committed.name}» изменён.`),
    ).toBeVisible();
    expect(screen.getAllByText(committed.name)).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Архив 1" })).toBeVisible();
    expect(updateProperty).toHaveBeenCalledWith({
      csrfToken: "csrf-token",
      propertyId: property.id,
      draft: {
        name: committed.name,
        shortName: "Дом",
        address: "Красноярск, ул. Мира, 1",
        expectedUpdatedAt: property.updatedAt,
      },
    });
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("archives only after explaining preserved history and unchanged rules", async () => {
    const user = userEvent.setup();
    const property = directory.items[0]!;
    const committed = archivedProperty(property, "2026-08-01T09:00:00Z");
    vi.mocked(changePropertyLifecycle).mockResolvedValue({
      status: "success",
      property: committed,
      impact: archiveImpact,
    });
    renderPage(directory);

    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    await user.click(screen.getByRole("button", { name: "В архив" }));

    const dialog = screen.getByRole("dialog", {
      name: "Перенести объект в архив?",
    });
    expect(
      within(dialog).getByText(/История, связанные операции и отчёты/),
    ).toBeVisible();
    expect(
      within(dialog).getByText(/правила останутся включены/),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        within(dialog).getByRole("button", { name: "Отмена" }),
      ).toHaveFocus(),
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Перенести в архив" }),
    );

    expect(changePropertyLifecycle).toHaveBeenCalledWith({
      action: "archive",
      csrfToken: "csrf-token",
      property,
    });
    expect(
      await screen.findByText(
        `Объект «${property.name}» перенесён в архив. История сохранена.`,
      ),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Активные 0" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Архив 2" })).toBeVisible();
    expect(screen.queryByText(property.name)).not.toBeInTheDocument();
  });

  it("restores directly from server capability and moves the committed row", async () => {
    const user = userEvent.setup();
    const property = directory.items[1]!;
    const committed = activeProperty(property, "2026-08-01T09:00:00Z");
    vi.mocked(changePropertyLifecycle).mockResolvedValue({
      status: "success",
      property: committed,
      impact: { ...archiveImpact, availableForNewReferences: true },
    });
    renderPage(directory, "/properties?view=archived");

    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    await user.click(screen.getByRole("button", { name: "Восстановить" }));

    expect(changePropertyLifecycle).toHaveBeenCalledWith({
      action: "restore",
      csrfToken: "csrf-token",
      property,
    });
    expect(
      await screen.findByText(`Объект «${property.name}» восстановлен.`),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Активные 2" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Архив 0" })).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Архив пока пуст" }),
    ).toBeVisible();
  });

  it("reloads an authoritative conflict snapshot before retrying lifecycle", async () => {
    const user = userEvent.setup();
    const property = directory.items[0]!;
    const fresh = { ...property, updatedAt: "2026-08-01T09:00:00Z" };
    const committed = archivedProperty(fresh, "2026-08-01T09:01:00Z");
    vi.mocked(changePropertyLifecycle)
      .mockResolvedValueOnce({
        status: "conflict",
        message: "Объект уже изменился. Обновите список.",
      })
      .mockResolvedValueOnce({
        status: "success",
        property: committed,
        impact: archiveImpact,
      });
    vi.mocked(loadProperties).mockResolvedValue({
      status: "success",
      directory: { ...directory, items: [fresh, directory.items[1]!] },
    });
    renderPage(directory);

    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    await user.click(screen.getByRole("button", { name: "В архив" }));
    await user.click(
      within(
        screen.getByRole("dialog", { name: "Перенести объект в архив?" }),
      ).getByRole("button", { name: "Перенести в архив" }),
    );

    expect(
      await screen.findByText("Объект уже изменился. Обновите список."),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Обновить и повторить" }),
    );

    await waitFor(() =>
      expect(changePropertyLifecycle).toHaveBeenLastCalledWith({
        action: "archive",
        csrfToken: "csrf-token",
        property: fresh,
      }),
    );
    expect(loadProperties).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByText(
        `Объект «${property.name}» перенесён в архив. История сохранена.`,
      ),
    ).toBeVisible();
  });
});

const archiveImpact = {
  historyPreserved: true,
  activeRulesUnchanged: true,
  availableForNewReferences: false,
};

function archivedProperty(
  property: PropertyDirectoryDto["items"][number],
  updatedAt: string,
): PropertyDirectoryDto["items"][number] {
  return {
    ...property,
    archivedAt: updatedAt,
    capabilities: { canUpdate: true, canArchive: false, canRestore: true },
    status: "archived",
    updatedAt,
  };
}

function activeProperty(
  property: PropertyDirectoryDto["items"][number],
  updatedAt: string,
): PropertyDirectoryDto["items"][number] {
  return {
    ...property,
    archivedAt: null,
    capabilities: { canUpdate: true, canArchive: true, canRestore: false },
    status: "active",
    updatedAt,
  };
}

function editButton(propertyId: string): HTMLButtonElement {
  return screen
    .getAllByRole("button", { name: "Изменить" })
    .find((button) =>
      button.getAttribute("aria-controls")?.includes(propertyId),
    ) as HTMLButtonElement;
}

function editField(
  propertyId: string,
  field: "name" | "shortName" | "address",
): HTMLElement {
  return document.querySelector(
    `[data-property-id="${propertyId}"][data-property-edit-field="${field}"]`,
  ) as HTMLElement;
}

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
    canViewRawImportData: true,
    canViewMemberDirectory: true,
    canManageMembers: true,
    canViewWorkspaceActivity: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};
