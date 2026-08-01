import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createCategory } from "./api/categories-api";
import { changeCategoryLifecycle } from "./api/category-detail-api";
import { CategoriesPage } from "./categories-page";
import { directory, session } from "./test-support";

vi.mock("./api/categories-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/categories-api")>();
  return { ...actual, createCategory: vi.fn() };
});

vi.mock("./api/category-detail-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/category-detail-api")>();
  return { ...actual, changeCategoryLifecycle: vi.fn() };
});

describe("CategoriesPage", () => {
  beforeEach(() => {
    vi.mocked(createCategory).mockReset();
    vi.mocked(changeCategoryLifecycle).mockReset();
  });

  it("renders a compact active directory with semantic category facts", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Категории" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Активные 2" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Архив 1" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Системные 1" })).toBeVisible();
    expect(screen.getAllByText("Продукты")).toHaveLength(2);
    expect(screen.getAllByText("Расход")).toHaveLength(2);
    expect(screen.getAllByText("12 операций")).toHaveLength(2);
    expect(screen.getAllByText("1 активных")).toHaveLength(2);
    expect(
      screen.getAllByRole("link", { name: "Открыть категорию «Продукты»" })[0],
    ).toHaveAttribute("href", `/categories/${directory.items[0]!.id}`);
    const productRow = screen.getAllByText("Продукты")[0]!.closest("tr");
    expect(productRow).not.toBeNull();
    expect(
      within(productRow!).getByText("Открыть").closest("a"),
    ).toHaveAttribute("href", `/categories/${directory.items[0]!.id}`);
    expect(screen.queryByText("Старые покупки")).not.toBeInTheDocument();
    expect(screen.queryByText("Без категории")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Новая категория" }),
    ).toBeVisible();
  });

  it("shows archived and system records from URL state", () => {
    const { unmount } = renderPage("/categories?view=archived");
    expect(screen.getAllByText("Старые покупки")).toHaveLength(2);
    expect(
      screen
        .getAllByText("Архив")
        .filter((label) => label.closest("[data-tone='neutral']")),
    ).toHaveLength(2);
    unmount();

    renderPage("/categories?view=system");
    expect(screen.getAllByText("Без категории")).toHaveLength(2);
    expect(screen.getAllByText("Системная")).toHaveLength(2);
    expect(screen.getAllByText("Смешанная")).toHaveLength(2);
  });

  it("archives a category from the directory after explicit confirmation", async () => {
    const user = userEvent.setup();
    const category = directory.items[1]!;
    const committed = {
      ...category,
      isActive: false,
      updatedAt: "2026-08-01T09:00:00Z",
      deleteBlockers: { ...category.deleteBlockers, reasonCodes: [] },
      capabilities: {
        ...category.capabilities,
        canArchive: false,
        canRestore: true,
        canDelete: true,
      },
    };
    vi.mocked(changeCategoryLifecycle).mockResolvedValue({
      status: "success",
      category: committed,
      impact: {
        historyPreserved: true,
        rulesUnchanged: true,
        availableForNewReferences: false,
      },
    });
    renderPage();

    const row = screen.getAllByText("Зарплата")[0]!.closest("tr");
    expect(row).not.toBeNull();
    await user.click(within(row!).getByRole("button", { name: "В архив" }));

    const dialog = screen.getByRole("dialog", {
      name: "Перенести категорию в архив?",
    });
    expect(
      within(dialog).getByText(/История, операции и отчёты/),
    ).toBeVisible();
    await user.click(
      within(dialog).getByRole("button", { name: "Перенести в архив" }),
    );

    expect(changeCategoryLifecycle).toHaveBeenCalledWith({
      action: "archive",
      category,
      csrfToken: "csrf-token",
    });
    expect(
      await screen.findByText(
        "Категория «Зарплата» перенесена в архив. История сохранена.",
      ),
    ).toBeVisible();
    expect(screen.queryByText("Зарплата")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Активные 1" })).toBeVisible();
  });

  it("explains an active-rule archive blocker without sending a mutation", async () => {
    const user = userEvent.setup();
    renderPage();

    const row = screen.getAllByText("Продукты")[0]!.closest("tr");
    expect(row).not.toBeNull();
    await user.click(within(row!).getByRole("button", { name: "В архив" }));

    expect(
      screen.getByText("Сначала отключите активные правила"),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Открыть правила" }),
    ).toHaveAttribute("href", `/rules?category_id=${directory.items[0]!.id}`);
    expect(changeCategoryLifecycle).not.toHaveBeenCalled();
  });

  it("restores an archived category directly from the directory", async () => {
    const user = userEvent.setup();
    const category = directory.items[2]!;
    const committed = {
      ...category,
      isActive: true,
      updatedAt: "2026-08-01T09:00:00Z",
      deleteBlockers: {
        ...category.deleteBlockers,
        reasonCodes: ["active_category" as const],
      },
      capabilities: {
        ...category.capabilities,
        canArchive: true,
        canRestore: false,
        canDelete: false,
      },
    };
    vi.mocked(changeCategoryLifecycle).mockResolvedValue({
      status: "success",
      category: committed,
      impact: {
        historyPreserved: true,
        rulesUnchanged: true,
        availableForNewReferences: true,
      },
    });
    renderPage("/categories?view=archived");

    const row = screen.getAllByText("Старые покупки")[0]!.closest("tr");
    expect(row).not.toBeNull();
    await user.click(
      within(row!).getByRole("button", { name: "Восстановить" }),
    );

    expect(changeCategoryLifecycle).toHaveBeenCalledWith({
      action: "restore",
      category,
      csrfToken: "csrf-token",
    });
    expect(
      await screen.findByText("Категория «Старые покупки» восстановлена."),
    ).toBeVisible();
    expect(screen.queryByText("Старые покупки")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Архив 0" })).toBeVisible();
  });

  it("announces a deletion carried through navigation state", async () => {
    renderPage({
      pathname: "/categories",
      search: "?view=archived",
      state: { categoryToast: "Категория «Черновик» удалена." },
    });

    expect(
      await screen.findByText("Категория «Черновик» удалена."),
    ).toBeVisible();
  });

  it("searches by localized kind and offers one reset path", async () => {
    const user = userEvent.setup();
    renderPage();

    const search = screen.getByRole("searchbox", {
      name: "Поиск по названию, типу или заметке",
    });
    await user.type(search, "перевод");
    await user.click(screen.getByRole("button", { name: "Найти" }));

    expect(
      screen.getByRole("heading", { name: "По этому запросу категорий нет" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Очистить поиск" })).toBeVisible();
  });

  it("keeps viewer access explicit without implying mutation authority", () => {
    renderPage("/categories", {
      ...directory,
      capabilities: {
        canCreate: false,
        readonlyReasonCode: "financial_write_forbidden",
      },
      items: directory.items.map((category) => ({
        ...category,
        capabilities: {
          canUpdate: false,
          canArchive: false,
          canRestore: false,
          canDelete: false,
          archiveBlockedReasonCode:
            category.capabilities.archiveBlockedReasonCode,
        },
      })),
    });

    expect(
      screen.getByText("Категории доступны только для просмотра"),
    ).toBeVisible();
    expect(screen.getAllByText("Продукты")).toHaveLength(2);
    expect(
      screen.queryByRole("button", { name: "Новая категория" }),
    ).toBeNull();
  });

  it("focuses an invalid name and protects a dirty draft", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Новая категория" }));
    expect(screen.getByText("Для обоих потоков.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Создать категорию" }));
    expect(screen.getByText("Введите название категории.")).toBeVisible();
    expect(screen.getByLabelText(/Название/)).toHaveFocus();
    expect(createCategory).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText(/Название/), "Черновик");
    await user.click(screen.getByRole("button", { name: "Отмена" }));
    expect(
      screen.getByRole("dialog", { name: "Закрыть создание категории?" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Продолжить создание" }),
    );
    expect(screen.getByLabelText(/Название/)).toHaveValue("Черновик");
  });

  it("keeps duplicate errors local and focuses the server-invalid field", async () => {
    const user = userEvent.setup();
    vi.mocked(createCategory).mockResolvedValue({
      status: "error",
      code: "category_validation_error",
      message: "Категория с таким названием уже есть.",
      fieldErrors: { name: ["Категория с таким названием уже есть."] },
    });
    renderPage();

    await user.click(screen.getByRole("button", { name: "Новая категория" }));
    await user.type(screen.getByLabelText(/Название/), "Продукты");
    await user.click(screen.getByRole("button", { name: "Создать категорию" }));

    expect(
      await screen.findAllByText("Категория с таким названием уже есть."),
    ).not.toHaveLength(0);
    await waitFor(() =>
      expect(screen.getByLabelText(/Название/)).toHaveFocus(),
    );
    expect(screen.getByLabelText(/Название/)).toHaveValue("Продукты");
  });

  it("inserts only committed state, closes, reports success and returns focus", async () => {
    const user = userEvent.setup();
    const committed = {
      ...directory.items[0]!,
      id: "af9366b6-8948-4a96-9280-7ee97712a50a",
      name: "Питомцы",
      notes: "Корм и ветеринар",
      operationCount: 0,
      ruleCount: 0,
      activeRuleCount: 0,
    };
    vi.mocked(createCategory).mockResolvedValue({
      status: "success",
      category: committed,
    });
    renderPage("/categories?view=archived&search=старые");

    const trigger = screen.getByRole("button", { name: "Новая категория" });
    await user.click(trigger);
    await user.type(screen.getByLabelText(/Название/), "Питомцы");
    await user.selectOptions(screen.getByLabelText(/Тип/), "expense");
    await user.type(screen.getByLabelText(/Заметка/), "Корм и ветеринар");
    await user.click(screen.getByRole("button", { name: "Создать категорию" }));

    expect(
      await screen.findByText("Категория «Питомцы» создана."),
    ).toBeVisible();
    await waitFor(() => expect(screen.getAllByText("Питомцы")).toHaveLength(2));
    expect(createCategory).toHaveBeenCalledWith({
      csrfToken: "csrf-token",
      draft: {
        name: "Питомцы",
        kind: "expense",
        notes: "Корм и ветеринар",
      },
    });
    expect(
      screen.queryByRole("dialog", { name: "Новая категория" }),
    ).not.toBeInTheDocument();
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});

function renderPage(
  initialEntry:
    | string
    | { pathname: string; search?: string; state?: unknown } = "/categories",
  categoryDirectory = directory,
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <CategoriesPage directory={categoryDirectory} session={session} />
    </MemoryRouter>,
  );
}
