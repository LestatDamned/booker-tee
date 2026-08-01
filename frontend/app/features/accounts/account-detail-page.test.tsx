import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import {
  updateImportedOperationReviewFields,
  type AccountDetailDto,
} from "./api/account-detail-api";
import { changeAccountLifecycle, updateAccount } from "./api/accounts-api";
import { AccountDetailPage } from "./account-detail-page";

vi.mock("./api/accounts-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/accounts-api")>();
  return {
    ...actual,
    changeAccountLifecycle: vi.fn(),
    updateAccount: vi.fn(),
  };
});

vi.mock("./api/account-detail-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/account-detail-api")>();
  return {
    ...actual,
    updateImportedOperationReviewFields: vi.fn(),
  };
});

describe("AccountDetailPage", () => {
  beforeEach(() => {
    vi.mocked(changeAccountLifecycle).mockReset();
    vi.mocked(updateAccount).mockReset();
    vi.mocked(updateImportedOperationReviewFields).mockReset();
  });

  it("renders the authoritative balance and account-relative movements", () => {
    renderPage(detail);

    expect(
      screen.getByRole("heading", { name: "Основной" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Все счета" })).toHaveAttribute(
      "href",
      "/accounts",
    );
    expect(screen.getByLabelText(/8.*500,00 RUB/)).toBeInTheDocument();
    expect(screen.getByLabelText(/−1.*500,00 RUB/)).toBeInTheDocument();
    expect(screen.getByText("Основной → Накопительный")).toBeInTheDocument();
    expect(screen.getByText("Не влияет на прибыль")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Открыть операцию" }),
    ).toHaveAttribute("href", expect.stringContaining("/app/ledger/manual"));
  });

  it("returns to the exact report context and keeps it while resetting filters", async () => {
    const user = userEvent.setup();
    const returnTo =
      "/app/reports?date_from=2026-07-01&date_to=2026-07-31&currency=RUB";
    renderPage(
      detail,
      `/app/accounts/id?date_from=2026-07-01&status=confirmed&return_to=${encodeURIComponent(returnTo)}`,
    );

    expect(
      screen.getByRole("link", { name: "Вернуться в отчёт" }),
    ).toHaveAttribute("href", returnTo);

    await user.click(screen.getByRole("button", { name: /^Показать фильтры/ }));
    const reset = new URL(
      screen.getByRole("link", { name: "Сбросить" }).getAttribute("href")!,
      "http://localhost",
    );
    expect(reset.pathname).toBe("/app/accounts/id");
    expect(reset.searchParams.get("return_to")).toBe(returnTo);
  });

  it("does not trust an external return target", () => {
    renderPage(
      detail,
      "/app/accounts/id?return_to=https%3A%2F%2Fevil.example%2Freports",
    );

    expect(screen.getByRole("link", { name: "Все счета" })).toHaveAttribute(
      "href",
      "/accounts",
    );
    expect(
      screen.queryByRole("link", { name: "Вернуться в отчёт" }),
    ).not.toBeInTheDocument();
  });

  it("uses shared pagination while preserving account filters in links", () => {
    renderPage(
      {
        ...detail,
        pagination: {
          page: 2,
          perPage: 25,
          total: 187,
          totalPages: 8,
          hasPrevious: true,
          hasNext: true,
        },
      },
      "/app/accounts/id?status=confirmed&page=2&per_page=25",
    );

    expect(
      screen.getByRole("navigation", { name: "Страницы проводок" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Страница 2")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Страница 3" })).toHaveAttribute(
      "href",
      "/app/accounts/id?status=confirmed&page=3&per_page=25",
    );
    expect(screen.getByText("26–50 из 187")).toBeVisible();
    expect(screen.getByLabelText("На странице")).toHaveValue("25");
  });

  it("opens filters and keeps explicit labels", async () => {
    const user = userEvent.setup();
    renderPage(detail);

    await user.click(screen.getByRole("button", { name: "Показать фильтры" }));

    expect(screen.getByLabelText("Статус")).toHaveValue("confirmed");
    expect(screen.getByLabelText("Дата от")).toBeInTheDocument();
    expect(screen.getByLabelText("Источник")).toBeInTheDocument();
    const reset = screen.getByRole("link", { name: "Сбросить" });
    const apply = screen.getByRole("button", { name: "Применить" });
    expect(reset).toHaveAttribute("data-tone", "secondary");
    expect(apply).toHaveAttribute("data-tone", "primary");
    expect(reset.parentElement).toHaveAttribute("data-layout", "split");
  });

  it("shows a useful filtered empty state without hiding the balance", () => {
    renderPage({ ...detail, items: [] }, "/app/accounts/id?search=такси");

    expect(
      screen.getByText("По этим фильтрам проводок нет"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/8.*500,00 RUB/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Сбросить все" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("list", { name: "Применённые фильтры" }),
    ).toHaveTextContent("Поиск: такси");
    expect(
      screen.getByRole("link", { name: "Сбросить фильтры" }),
    ).toHaveAttribute("href", "/app/accounts/id");
  });

  it("opens settings from the account header and saves a stale-safe draft", async () => {
    const user = userEvent.setup();
    vi.mocked(updateAccount).mockResolvedValue({
      status: "success",
      account: {
        id: detail.account.id,
        name: "Расчётный",
        accountType: "checking",
        currency: "RUB",
        initialBalance: "12000.00",
        balance: "10500.00",
        balanceDirection: "positive",
        movementCount: 1,
        isActive: true,
        updatedAt: "2026-07-30T12:05:00Z",
        capabilities: { canArchive: true, canRestore: false },
      },
    });
    renderPage(detail);

    await user.click(screen.getByRole("button", { name: "Настройки счёта" }));
    expect(
      screen.getByRole("dialog", { name: "Настройки счёта" }),
    ).toBeInTheDocument();
    const cancel = screen.getByRole("button", { name: "Отмена" });
    const save = screen.getByRole("button", { name: "Сохранить изменения" });
    expect(cancel.parentElement).toHaveAttribute("data-layout", "split");
    expect(cancel.parentElement).toHaveAttribute("data-sticky", "true");
    expect(cancel).toHaveAttribute("data-tone", "secondary");
    expect(save.querySelector("svg")).toBeInTheDocument();
    expect(cancel.compareDocumentPosition(save)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    await user.clear(screen.getByLabelText(/Название/));
    await user.type(screen.getByLabelText(/Название/), "Расчётный");
    await user.selectOptions(screen.getByLabelText(/Тип/), "checking");
    await user.clear(screen.getByLabelText(/Начальный баланс/));
    await user.type(screen.getByLabelText(/Начальный баланс/), "12000.00");
    await user.click(
      screen.getByRole("button", { name: "Сохранить изменения" }),
    );

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Расчётный" }),
      ).toBeInTheDocument(),
    );
    expect(updateAccount).toHaveBeenCalledWith({
      accountId: detail.account.id,
      csrfToken: "csrf-token",
      draft: {
        accountType: "checking",
        currency: "RUB",
        expectedUpdatedAt: "2026-07-30T12:00:00Z",
        initialBalance: "12000.00",
        name: "Расчётный",
      },
    });
    expect(screen.getByText("Настройки счёта сохранены.")).toBeInTheDocument();
  });

  it("protects a dirty settings draft from accidental close", async () => {
    const user = userEvent.setup();
    renderPage(detail);

    await user.click(screen.getByRole("button", { name: "Настройки счёта" }));
    await user.type(screen.getByLabelText(/Название/), " 2");
    await user.click(screen.getByRole("button", { name: "Закрыть" }));

    expect(
      screen.getByRole("dialog", { name: "Закрыть настройки?" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Продолжить редактирование" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Настройки счёта" }),
    ).toBeInTheDocument();
  });

  it("archives from settings only after explaining what stays", async () => {
    const user = userEvent.setup();
    vi.mocked(changeAccountLifecycle).mockResolvedValue({
      status: "success",
      account: {
        id: detail.account.id,
        name: detail.account.name,
        accountType: detail.account.accountType,
        currency: detail.account.currency,
        initialBalance: detail.account.initialBalance,
        balance: detail.account.balance,
        balanceDirection: "positive",
        movementCount: 1,
        isActive: false,
        updatedAt: "2026-07-30T12:05:00Z",
        capabilities: { canArchive: false, canRestore: true },
      },
    });
    renderPage(detail);

    await user.click(screen.getByRole("button", { name: "Настройки счёта" }));
    await user.click(screen.getByRole("button", { name: "Перенести в архив" }));

    expect(
      screen.getByText(/История и баланс счёта .* сохранятся/),
    ).toBeInTheDocument();
    const archiveButtons = screen.getAllByRole("button", {
      name: "Перенести в архив",
    });
    await user.click(archiveButtons.at(-1)!);
    await waitFor(() =>
      expect(screen.getByText(/в архиве/)).toBeInTheDocument(),
    );
    expect(changeAccountLifecycle).toHaveBeenCalledWith({
      account: detail.account,
      action: "archive",
      csrfToken: "csrf-token",
    });
  });

  it("edits only review fields of an imported operation and reconciles the row", async () => {
    const user = userEvent.setup();
    const movement = importedDetail.items[0]!;
    vi.mocked(updateImportedOperationReviewFields).mockResolvedValue({
      status: "success",
      movement: {
        ...movement,
        version: 4,
        description: "Такси до аэропорта",
        category: importedDetail.filterOptions.categories[0]!,
        property: importedDetail.filterOptions.properties[0]!,
      },
    });
    renderPage(importedDetail);

    expect(
      screen.getByRole("link", { name: "Открыть импорт" }),
    ).toBeInTheDocument();
    const editButton = screen.getByRole("button", { name: "Исправить" });
    await user.click(editButton);

    const correction = screen.getByRole("region", {
      name: "Исправить операцию",
    });
    expect(correction).toBeInTheDocument();
    expect(correction).toHaveAttribute("data-workbench-row-expansion");
    expect(correction.closest("article")).toHaveAttribute(
      "id",
      `operation-${movement.operationId}`,
    );
    expect(correction.closest("article")).toHaveAttribute(
      "data-state",
      "working",
    );
    expect(screen.getByRole("button", { name: "Закрыть" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(
      within(correction).queryByText("Сумма, дата и проводки не изменятся"),
    ).not.toBeInTheDocument();
    expect(within(correction).queryByRole("link")).not.toBeInTheDocument();
    expect(
      within(correction).getByRole("combobox", { name: "Категория" }),
    ).toHaveAttribute("placeholder", "Найти категорию");
    expect(within(correction).getByLabelText("Описание")).toHaveProperty(
      "tagName",
      "INPUT",
    );
    const actions = within(correction)
      .getAllByRole("button")
      .filter((button) =>
        ["Отмена", "Сохранить исправления"].includes(button.textContent ?? ""),
      );
    expect(actions.map((button) => button.textContent)).toEqual([
      "Отмена",
      "Сохранить исправления",
    ]);
    expect(actions[0]).toHaveAttribute("data-tone", "secondary");
    expect(actions[1]?.querySelector("svg")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Описание"));
    await user.type(screen.getByLabelText("Описание"), "Такси до аэропорта");
    await user.click(screen.getByRole("combobox", { name: "Категория" }));
    await user.type(
      screen.getByRole("combobox", { name: "Категория" }),
      "тран",
    );
    await user.click(screen.getByRole("option", { name: "Транспорт" }));
    await user.selectOptions(
      screen.getByLabelText("Объект"),
      importedDetail.filterOptions.properties[0]!.id,
    );
    await user.click(
      screen.getByRole("button", { name: "Сохранить исправления" }),
    );

    await waitFor(() =>
      expect(screen.getByText("Такси до аэропорта")).toBeInTheDocument(),
    );
    expect(screen.getByText("Транспорт")).toBeInTheDocument();
    expect(screen.getByText("Объект: Квартира")).toBeInTheDocument();
    expect(screen.getByLabelText(/−881,12 RUB/)).toBeInTheDocument();
    expect(updateImportedOperationReviewFields).toHaveBeenCalledWith({
      accountId: importedDetail.account.id,
      csrfToken: "csrf-token",
      operationId: movement.operationId,
      draft: {
        categoryId: importedDetail.filterOptions.categories[0]!.id,
        description: "Такси до аэропорта",
        expectedVersion: 3,
        propertyId: importedDetail.filterOptions.properties[0]!.id,
      },
    });
  });

  it("keeps the correction draft when the operation changed elsewhere", async () => {
    const user = userEvent.setup();
    vi.mocked(updateImportedOperationReviewFields).mockResolvedValue({
      status: "conflict",
      code: "operation_version_conflict",
      message: "Операция уже изменилась. Загрузите актуальные данные.",
    });
    renderPage(importedDetail);

    await user.click(screen.getByRole("button", { name: "Исправить" }));
    await user.clear(screen.getByLabelText("Описание"));
    await user.type(screen.getByLabelText("Описание"), "Мой черновик");
    await user.click(
      screen.getByRole("button", { name: "Сохранить исправления" }),
    );

    expect(
      await screen.findByText(
        "Операция уже изменилась. Загрузите актуальные данные.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Описание")).toHaveValue("Мой черновик");
    expect(
      screen.getByRole("button", { name: "Загрузить актуальные данные" }),
    ).toBeInTheDocument();
  });

  it("protects an inline correction draft when the row is closed", async () => {
    const user = userEvent.setup();
    renderPage(importedDetail);

    await user.click(screen.getByRole("button", { name: "Исправить" }));
    await user.type(screen.getByLabelText("Описание"), " уточнено");
    await user.click(screen.getByRole("button", { name: "Закрыть" }));

    expect(
      screen.getByRole("dialog", { name: "Закрыть исправление?" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Продолжить редактирование" }),
    );
    expect(
      screen.getByRole("region", { name: "Исправить операцию" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Описание")).toHaveValue("Поездка уточнено");
  });

  it("does not show mutation controls to a viewer", () => {
    renderPage({
      ...detail,
      account: {
        ...detail.account,
        capabilities: {
          canUpdate: false,
          canArchive: false,
          canRestore: false,
        },
      },
    });

    expect(
      screen.queryByRole("button", { name: "Настройки счёта" }),
    ).not.toBeInTheDocument();
  });
});

function renderPage(
  current: AccountDetailDto,
  initialEntry = "/app/accounts/id",
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AccountDetailPage detail={current} session={session} />
    </MemoryRouter>,
  );
}

const detail: AccountDetailDto = {
  account: {
    id: "285c18d8-78bb-46d7-b6cd-d6fc897ab8a2",
    name: "Основной",
    accountType: "card",
    currency: "RUB",
    initialBalance: "10000.00",
    balance: "8500.00",
    isActive: true,
    updatedAt: "2026-07-30T12:00:00Z",
    capabilities: {
      canUpdate: true,
      canArchive: true,
      canRestore: false,
    },
  },
  items: [
    {
      operationId: "af63a90b-d3ea-4698-b4bf-a393c942d4fa",
      version: 3,
      operationType: "transfer",
      operationDate: "2026-07-29",
      description: "В резерв",
      status: "confirmed",
      source: "manual",
      amount: "-1500.00",
      currency: "RUB",
      category: null,
      property: null,
      transferRoute: "Основной → Накопительный",
      sourceTarget: {
        kind: "manual",
        uploadedDocumentId: null,
        rawTransactionId: null,
      },
      capabilities: {
        canEditReviewFields: false,
        readonlyReasonCode: "imported_operation_only",
      },
    },
  ],
  pagination: {
    page: 1,
    perPage: 25,
    total: 1,
    totalPages: 1,
    hasPrevious: false,
    hasNext: false,
  },
  filterOptions: {
    categories: [],
    properties: [],
    perPage: [25, 50, 100, 200],
  },
};

const importedDetail: AccountDetailDto = {
  ...detail,
  items: [
    {
      operationId: "bf33efda-0f29-45ef-9253-b2c9e05e9998",
      version: 3,
      operationType: "expense",
      operationDate: "2026-07-29",
      description: "Поездка",
      status: "confirmed",
      source: "bank_pdf",
      amount: "-881.12",
      currency: "RUB",
      category: null,
      property: null,
      transferRoute: null,
      sourceTarget: {
        kind: "import",
        uploadedDocumentId: "d0f6ed6c-73db-4df0-a31d-ef46896836ae",
        rawTransactionId: "9e9b80bc-aeed-43f7-8f60-c85fe871410e",
      },
      capabilities: {
        canEditReviewFields: true,
        readonlyReasonCode: null,
      },
    },
  ],
  filterOptions: {
    ...detail.filterOptions,
    categories: [
      {
        id: "12b1a936-003d-4e93-946d-1e6eeac7b672",
        name: "Транспорт",
      },
    ],
    properties: [
      {
        id: "f408af9d-f2bb-4690-993a-4ba8a25c7c04",
        name: "Квартира",
      },
    ],
  },
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
