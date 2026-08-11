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

  it("renders debt facts without inventing overdue state", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: "Кредит на ремонт" }),
    ).toBeVisible();
    expect(screen.getByText("Конечный срок")).toBeVisible();
    expect(screen.queryByText(/Просроч/)).not.toBeInTheDocument();
    expect(screen.getByText("Основной долг")).toBeVisible();
    expect(screen.getByText("Проценты")).toBeVisible();
    expect(screen.getByRole("button", { name: "Отменить" })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Открыть основную операцию" }),
    ).toHaveAttribute(
      "href",
      `/operations?operation_id=${detail.payments.items[0]!.principal!.operationId}#operation-${detail.payments.items[0]!.principal!.operationId}`,
    );
    expect(
      screen.getByRole("link", { name: "Открыть операцию процентов" }),
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

    await user.click(screen.getByRole("button", { name: "Записать платёж" }));
    const dialog = screen.getByRole("dialog", { name: "Записать платёж" });
    await user.clear(within(dialog).getByLabelText(/Основной долг/));
    await user.type(within(dialog).getByLabelText(/Основной долг/), "5000");
    await user.clear(within(dialog).getByLabelText(/Проценты/));
    await user.type(within(dialog).getByLabelText(/Проценты/), "1000");
    await user.selectOptions(
      within(dialog).getByLabelText(/Денежный счёт/),
      account.id,
    );
    await user.selectOptions(
      within(dialog).getByLabelText(/Категория расхода/),
      expenseCategory.id,
    );

    expect(screen.getByText("Основной долг уменьшится на")).toBeVisible();
    expect(screen.getByText("Проценты станут расходом")).toBeVisible();
    await user.click(
      within(dialog).getByRole("button", { name: "Записать платёж" }),
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

  it("undoes only when the server capability allows it", async () => {
    const user = userEvent.setup();
    vi.mocked(undoDebtPayment).mockResolvedValue({ status: "success", detail });
    renderPage();

    await user.click(screen.getByRole("button", { name: "Отменить" }));
    await user.click(screen.getByRole("button", { name: "Отменить платёж" }));

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
    await user.click(screen.getByRole("button", { name: "Удалить" }));

    expect(
      screen.getByText(
        /Долг уже имеет платежи, импорт или последующие операции/,
      ),
    ).toBeVisible();
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

function renderPage(value = detail) {
  return render(
    <MemoryRouter initialEntries={[`/debts/${value.debt.accountId}`]}>
      <DebtDetailPage
        accounts={[account]}
        categories={[expenseCategory]}
        detail={value}
        session={session}
      />
    </MemoryRouter>,
  );
}
