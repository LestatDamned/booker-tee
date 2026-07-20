import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import type { ManualLedgerDto } from "./manual-ledger-api";
import { ManualLedgerPage } from "./manual-ledger-page";

afterEach(() => vi.unstubAllGlobals());

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

  it("locks conflicting actions on one row while leaving unrelated UI available", async () => {
    const user = userEvent.setup();
    const page = ledger();
    let resolveRequest: ((response: Response) => void) | undefined;
    const pendingResponse = new Promise<Response>((resolve) => {
      resolveRequest = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pendingResponse);
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter initialEntries={["/app/ledger/manual"]}>
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    const cancel = screen.getByRole("button", { name: "Отменить операцию" });
    fireEvent.click(cancel);
    fireEvent.click(cancel);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Исправить" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Добавить операцию" }),
    ).toBeEnabled();

    const cancelled = {
      ...page.items[0],
      version: 4,
      status: "ignored" as const,
      capabilities: {
        canEdit: false,
        canCancel: false,
        canRestore: true,
        canDelete: true,
        readonlyReason: null,
      },
    };
    resolveRequest?.(jsonResponse(cancelled, 200));

    await user.click(
      await screen.findByRole("button", { name: "Восстановить операцию" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
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

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
