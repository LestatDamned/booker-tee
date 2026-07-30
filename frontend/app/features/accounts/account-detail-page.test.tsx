import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { SessionDto } from "../../api/session";
import type { AccountDetailDto } from "./api/account-detail-api";
import { AccountDetailPage } from "./account-detail-page";

describe("AccountDetailPage", () => {
  it("renders the authoritative balance and account-relative movements", () => {
    renderPage(detail);

    expect(
      screen.getByRole("heading", { name: "Основной" }),
    ).toBeInTheDocument();
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
