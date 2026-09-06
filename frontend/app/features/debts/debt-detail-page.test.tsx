import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  changeDebtLifecycle,
  deleteDebt,
  recordDebtPayment,
  undoDebtPayment,
  updateDebt,
} from "./api/debts-api";
import { DebtDetailPage } from "./debt-detail-page";
import { account, detail, expenseCategory, session } from "./test-support";

vi.mock("./api/debts-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/debts-api")>();
  return {
    ...actual,
    changeDebtLifecycle: vi.fn(),
    deleteDebt: vi.fn(),
    recordDebtPayment: vi.fn(),
    undoDebtPayment: vi.fn(),
    updateDebt: vi.fn(),
  };
});

describe("DebtDetailPage", () => {
  beforeEach(() => {
    vi.mocked(changeDebtLifecycle).mockReset();
    vi.mocked(deleteDebt).mockReset();
    vi.mocked(recordDebtPayment).mockReset();
    vi.mocked(undoDebtPayment).mockReset();
    vi.mocked(updateDebt).mockReset();
  });

  it("renders debt facts without inventing overdue state", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(
      screen.getByRole("heading", { name: "Кредит на ремонт" }),
    ).toBeVisible();
    expect(screen.getByText("Конечный срок")).not.toBeVisible();
    await user.click(screen.getByRole("button", { name: "Условия и заметки" }));
    expect(screen.getByText("Конечный срок")).toBeVisible();
    expect(screen.getAllByText("Условия и заметки")).toHaveLength(1);
    expect(screen.queryByText(/Просроч/)).not.toBeInTheDocument();
    expect(screen.getByText("Основной долг")).toBeVisible();
    expect(screen.getByText("Проценты")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Отменить платёж" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Посмотреть перевод" }),
    ).toHaveAttribute(
      "href",
      `/operations?operation_id=${detail.payments.items[0]!.principal!.operationId}#operation-${detail.payments.items[0]!.principal!.operationId}`,
    );
    expect(
      screen.getByRole("link", { name: "Посмотреть проценты" }),
    ).toHaveAttribute(
      "href",
      `/operations?operation_id=${detail.payments.items[0]!.interest!.operationId}#operation-${detail.payments.items[0]!.interest!.operationId}`,
    );
  });

  it("previews and records principal and interest together", async () => {
    const user = userEvent.setup();
    vi.mocked(recordDebtPayment).mockResolvedValue({
      status: "success",
      detail,
    });
    renderPage();

    await user.click(
      screen.getByRole("button", { name: "Записать погашение" }),
    );
    const dialog = screen.getByRole("dialog", { name: "Записать погашение" });
    await user.clear(within(dialog).getByLabelText(/Основной долг/));
    await user.type(within(dialog).getByLabelText(/Основной долг/), "5000");
    await user.clear(within(dialog).getByLabelText(/Проценты/));
    await user.type(within(dialog).getByLabelText(/Проценты/), "1000");
    await user.selectOptions(
      within(dialog).getByLabelText(/С какого счёта/),
      account.id,
    );
    await user.selectOptions(
      within(dialog).getByLabelText(/Категория расхода/),
      expenseCategory.id,
    );

    expect(screen.getByText("Основной долг уменьшится на")).toBeVisible();
    expect(screen.getByText("Проценты станут расходом")).toBeVisible();
    expect(within(dialog).getByLabelText(/6.*000,00 RUB/)).toBeVisible();
    expect(within(dialog).getByLabelText(/70.*000,00 RUB/)).toBeVisible();
    await user.click(
      within(dialog).getByRole("button", { name: "Записать погашение" }),
    );

    await waitFor(() =>
      expect(recordDebtPayment).toHaveBeenCalledWith(
        detail.debt.accountId,
        expect.objectContaining({
          interestAmount: "1000",
          interestCategoryId: expenseCategory.id,
          principalAmount: "5000",
          settlementAccountId: account.id,
        }),
        "csrf-token",
        expect.any(String),
      ),
    );
  });

  it("preserves list filters through history pagination and back navigation", () => {
    renderPage(
      {
        ...detail,
        payments: {
          ...detail.payments,
          hasNext: true,
          totalPages: 2,
          total: 21,
        },
      },
      "?view=archived&search=кредит",
    );
    expect(screen.getByRole("link", { name: "Все долги" })).toHaveAttribute(
      "href",
      "/debts?view=archived&search=%D0%BA%D1%80%D0%B5%D0%B4%D0%B8%D1%82",
    );
    const next = screen
      .getAllByRole("link")
      .find((link) => link.getAttribute("href")?.includes("page=2"));
    expect(next?.getAttribute("href")).toContain("view=archived");
    expect(next?.getAttribute("href")).toContain("search=");
  });

  it("previews incoming cents exactly and rejects overpayment", async () => {
    const user = userEvent.setup();
    renderPage({
      ...detail,
      debt: { ...detail.debt, kind: "loan_receivable", outstanding: "0.30" },
    });
    await user.click(screen.getByRole("button", { name: "Записать возврат" }));
    const dialog = screen.getByRole("dialog", { name: "Записать возврат" });
    const principal = within(dialog).getByLabelText(/Основной долг/);
    const interest = within(dialog).getByLabelText(/Проценты/);
    await user.clear(principal);
    await user.type(principal, "0,10");
    await user.clear(interest);
    await user.type(interest, "0,20");
    expect(within(dialog).getByText("Всего поступит на счёт")).toBeVisible();
    expect(within(dialog).getByLabelText("0,30 RUB")).toBeVisible();
    await user.clear(principal);
    await user.type(principal, "0,31");
    await user.click(
      within(dialog).getByRole("button", { name: "Записать возврат" }),
    );
    expect(principal).toHaveFocus();
    expect(principal).toHaveAccessibleDescription(
      "Сумма больше остатка основного долга.",
    );
    expect(recordDebtPayment).not.toHaveBeenCalled();
  });

  it("links edit validation to the invalid field", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Ещё действия" }));
    await user.click(screen.getByRole("button", { name: "Изменить" }));
    const name = screen.getByLabelText("Название *");
    await user.clear(name);
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(name).toHaveFocus();
    expect(name).toHaveAccessibleDescription("Укажите название долга.");
    expect(updateDebt).not.toHaveBeenCalled();
  });

  it("undoes only when the server capability allows it", async () => {
    const user = userEvent.setup();
    vi.mocked(undoDebtPayment).mockResolvedValue({ status: "success", detail });
    renderPage();

    await user.click(screen.getByRole("button", { name: "Отменить платёж" }));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Отменить платёж",
      }),
    );

    await waitFor(() =>
      expect(undoDebtPayment).toHaveBeenCalledWith(
        detail.payments.items[0],
        "csrf-token",
      ),
    );
  });

  it("archives a settled debt through its server capability", async () => {
    const user = userEvent.setup();
    const settled = {
      ...detail,
      debt: {
        ...detail.debt,
        balance: "0.00",
        capabilities: {
          canArchive: true,
          canDelete: false,
          canRecordPayment: false,
          canRestore: false,
          canUpdate: true,
          deleteBlockedReason: "financial_history" as const,
          paymentBlockedReason: "debt_settled" as const,
        },
        outstanding: "0.00",
        status: "settled" as const,
      },
    };
    vi.mocked(changeDebtLifecycle).mockResolvedValue({
      status: "success",
      detail: settled,
    });
    renderPage(settled);
    expect(screen.getByText("Долг погашен")).toBeVisible();
    expect(screen.queryByText("Должен я")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Новый платёж сейчас недоступен"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "Страницы истории платежей" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "В архив" }));
    await user.click(screen.getByRole("button", { name: "Перенести в архив" }));

    await waitFor(() =>
      expect(changeDebtLifecycle).toHaveBeenCalledWith(
        settled.debt,
        "archive",
        "csrf-token",
      ),
    );
  });

  it("explains why a debt with later history cannot be deleted", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Ещё действия" }));
    expect(screen.getByRole("button", { name: "Удалить" })).toBeDisabled();

    expect(screen.getByText("Есть финансовая история")).toBeVisible();
    expect(deleteDebt).not.toHaveBeenCalled();
  });

  it("edits safe fields and deletes only through server capabilities", async () => {
    const user = userEvent.setup();
    const unused = {
      ...detail,
      debt: {
        ...detail.debt,
        capabilities: {
          ...detail.debt.capabilities,
          canDelete: true,
          deleteBlockedReason: null,
        },
      },
    };
    vi.mocked(updateDebt).mockResolvedValue({
      status: "success",
      detail: unused,
    });
    vi.mocked(deleteDebt).mockResolvedValue({
      status: "success",
      deletedId: unused.debt.accountId,
      name: unused.debt.name,
    });
    renderPage(unused);

    await user.click(screen.getByRole("button", { name: "Ещё действия" }));
    await user.click(screen.getByRole("button", { name: "Изменить" }));
    const form = screen.getByRole("dialog", { name: "Изменить долг" });
    await user.clear(within(form).getByLabelText("Название *"));
    await user.type(within(form).getByLabelText("Название *"), "Новый кредит");
    await user.clear(within(form).getByLabelText("Заметки"));
    await user.type(
      within(form).getByLabelText("Заметки"),
      "Комментарий с пробелами",
    );
    await user.click(within(form).getByRole("button", { name: "Сохранить" }));

    await waitFor(() =>
      expect(updateDebt).toHaveBeenCalledWith(
        unused.debt.accountId,
        expect.objectContaining({
          expectedUpdatedAt: unused.debt.updatedAt,
          name: "Новый кредит",
          notes: "Комментарий с пробелами",
        }),
        "csrf-token",
      ),
    );

    await user.click(screen.getByRole("button", { name: "Ещё действия" }));
    await user.click(screen.getByRole("button", { name: "Удалить" }));
    await user.click(screen.getByRole("button", { name: "Удалить долг" }));
    await waitFor(() =>
      expect(deleteDebt).toHaveBeenCalledWith(unused.debt, "csrf-token"),
    );
  });
});

function renderPage(value = detail, search = "") {
  return render(
    <MemoryRouter initialEntries={[`/debts/${value.debt.accountId}${search}`]}>
      <DebtDetailPage
        accounts={[account]}
        categories={[expenseCategory]}
        detail={value}
        session={session}
      />
    </MemoryRouter>,
  );
}
