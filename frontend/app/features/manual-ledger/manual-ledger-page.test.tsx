import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { SessionDto } from "../../api/session";
import type { ManualLedgerDto } from "./manual-ledger-api";
import { ManualLedgerPage } from "./manual-ledger-page";

describe("ManualLedgerPage", () => {
  it("renders date, money and the single backend description as primary data", () => {
    render(
      <MemoryRouter initialEntries={["/app/ledger/manual"]}>
        <ManualLedgerPage ledger={ledger()} session={session} />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "Ручные операции" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Аренда за июль" }),
    ).toBeInTheDocument();
    expect(screen.getByText("20.07.2026")).toBeInTheDocument();
    expect(screen.getByLabelText("−65 000,00 RUB")).toBeInTheDocument();
    expect(screen.getByText("расход")).toBeInTheDocument();
  });

  it("preserves applied filters when building pagination URLs", () => {
    const page = ledger();
    page.pagination = {
      page: 1,
      perPage: 25,
      total: 30,
      totalPages: 2,
      hasPrevious: false,
      hasNext: true,
    };
    render(
      <MemoryRouter
        initialEntries={["/app/ledger/manual?type=expense&page=1&per_page=25"]}
      >
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Дальше" })).toHaveAttribute(
      "href",
      "/app/ledger/manual?type=expense&page=2&per_page=25",
    );
  });

  it("marks the operation selected by a deep link as the target row", () => {
    const page = ledger();
    render(
      <MemoryRouter initialEntries={["/app/ledger/manual"]}>
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    expect(
      document.getElementById(`operation-${page.targetOperationId}`),
    ).toHaveAttribute("data-state", "target");
  });
});

const session: SessionDto = {
  user: { id: crypto.randomUUID(), email: "max@example.test", name: "Max" },
  workspace: {
    id: crypto.randomUUID(),
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

function ledger(): ManualLedgerDto {
  const operationId = crypto.randomUUID();
  return {
    items: [
      {
        id: operationId,
        version: 3,
        operationDate: "2026-07-20",
        description: "Аренда за июль",
        status: "confirmed",
        money: {
          amount: "65000.00",
          currency: "RUB",
          operationType: "expense",
          entryDirection: "outflow",
        },
        account: { id: crypto.randomUUID(), name: "Основной счёт" },
        sourceAccount: null,
        destinationAccount: null,
        category: null,
        property: null,
        capabilities: {
          canEdit: true,
          canCancel: true,
          canRestore: false,
          canDelete: false,
          readonlyReason: null,
        },
      },
    ],
    pagination: {
      page: 1,
      perPage: 50,
      total: 1,
      totalPages: 1,
      hasPrevious: false,
      hasNext: false,
    },
    filterOptions: {
      accounts: [
        { id: crypto.randomUUID(), name: "Основной счёт", currency: "RUB" },
      ],
      categories: [],
      properties: [],
      perPage: [25, 50, 100, 200],
    },
    capabilities: { canCreate: true, readonlyReason: null },
    targetOperationId: operationId,
  };
}
