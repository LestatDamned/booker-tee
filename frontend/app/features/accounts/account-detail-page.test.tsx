import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import type { AccountDetailDto } from "./api/account-detail-api";
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

describe("AccountDetailPage", () => {
  beforeEach(() => {
    vi.mocked(changeAccountLifecycle).mockReset();
    vi.mocked(updateAccount).mockReset();
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

  it("opens filters and keeps explicit labels", async () => {
    const user = userEvent.setup();
    renderPage(detail);

    await user.click(screen.getByRole("button", { name: "Показать фильтры" }));

    expect(screen.getByLabelText("Статус")).toHaveValue("confirmed");
    expect(screen.getByLabelText("Дата от")).toBeInTheDocument();
    expect(screen.getByLabelText("Источник")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Применить" }),
    ).toBeInTheDocument();
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
