import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../../api/session";
import tagStyles from "../../../ui/tag/tag.module.css";
import type { OperationsDto } from "../../operations/api/operations-api";
import { ManualLedgerPage } from "./manual-ledger-page";

afterEach(() => vi.unstubAllGlobals());

describe("OperationsPage", () => {
  it("renders date, money and the single backend description as primary data", () => {
    render(
      <MemoryRouter initialEntries={["/app/operations"]}>
        <ManualLedgerPage ledger={ledger()} session={session} />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "Операции" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Аренда за июль" }),
    ).toBeInTheDocument();
    expect(screen.getByText("20.07.2026")).toBeInTheDocument();
    expect(screen.getByLabelText("−65 000,00 RUB")).toBeInTheDocument();
    expect(screen.getByText("Расход")).toBeInTheDocument();
  });

  it("renders category metadata in the shared category tone", () => {
    const page = ledger();
    page.items[0] = {
      ...required(page.items[0], "fixture operation"),
      category: { id: crypto.randomUUID(), name: "Аренда" },
    };
    render(
      <MemoryRouter initialEntries={["/app/operations?type=expense"]}>
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Аренда")).toBeInTheDocument();
    expect(screen.getByText("Аренда")).toHaveClass(
      required(tagStyles.category, "category tag class"),
    );
  });

  it("shows a compact transfer route without a repeated profit explanation", () => {
    const page = ledger();
    page.items[0] = {
      ...required(page.items[0], "fixture operation"),
      operationType: "transfer",
      money: {
        amount: "15000.00",
        currency: "RUB",
      },
      account: null,
      category: null,
      sourceAccount: {
        id: crypto.randomUUID(),
        name: "ВТБ вклад",
        currency: "RUB",
      },
      destinationAccount: {
        id: crypto.randomUUID(),
        name: "Экспобанк карта",
        currency: "RUB",
      },
    };

    render(
      <MemoryRouter initialEntries={["/app/operations"]}>
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );
    expect(
      document.getElementById(`operation-${page.items[0]?.id}`),
    ).toHaveTextContent("ВТБ вклад → Экспобанк карта · Вручную");
    expect(screen.queryByText("Не влияет на прибыль")).not.toBeInTheDocument();
  });

  it("offers a recovery action when filters leave no visible operations", () => {
    const page = ledger();
    page.items = [];
    page.pagination = {
      page: 1,
      perPage: 50,
      total: 0,
      totalPages: 1,
      hasPrevious: false,
      hasNext: false,
    };
    page.targetOperationId = null;

    render(
      <MemoryRouter
        initialEntries={["/app/operations?type=expense&search=аренда"]}
      >
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("status")).toHaveAttribute("data-kind", "filtered");
    expect(
      screen.getByRole("list", { name: "Применённые фильтры" }),
    ).toHaveTextContent("Тип: расход");
    expect(
      screen.getByRole("list", { name: "Применённые фильтры" }),
    ).toHaveTextContent("Поиск: аренда");
    expect(
      screen.getByRole("link", { name: "Сбросить фильтры" }),
    ).toHaveAttribute("href", "/app/operations");
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
        initialEntries={["/app/operations?type=expense&page=1&per_page=25"]}
      >
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Дальше" })).toHaveAttribute(
      "href",
      "/app/operations?type=expense&page=2&per_page=25",
    );
  });

  it("preserves filters and resets pagination when density changes", async () => {
    const user = userEvent.setup();
    const page = ledger();
    page.pagination = {
      page: 3,
      perPage: 50,
      total: 120,
      totalPages: 3,
      hasPrevious: true,
      hasNext: false,
    };

    render(
      <MemoryRouter
        initialEntries={["/app/operations?type=expense&page=3&per_page=50"]}
      >
        <ManualLedgerPage ledger={page} session={session} />
        <LocationProbe />
      </MemoryRouter>,
    );

    await user.selectOptions(screen.getByLabelText("На странице"), "100");

    expect(screen.getByTestId("location-search")).toHaveTextContent(
      "type=expense&page=1&per_page=100",
    );
  });

  it("renders the operation selected by a deep link without a permanent state", () => {
    const page = ledger();
    page.targetOperationId = required(page.items[0], "fixture operation").id;
    render(
      <MemoryRouter initialEntries={["/app/operations"]}>
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    expect(
      document.getElementById(`operation-${page.targetOperationId}`),
    ).toHaveAttribute("data-state", "target");
    expect(screen.queryByText("Текущая строка")).not.toBeInTheDocument();
  });

  it("renders a targeted operation outside the current page", () => {
    const page = ledger();
    const target = {
      ...required(page.items[0], "fixture operation"),
      id: crypto.randomUUID(),
      description: "Старая целевая операция",
    };
    page.targetOperationId = target.id;
    page.targetOperation = target;

    render(
      <MemoryRouter initialEntries={[`/app/operations#operation-${target.id}`]}>
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Старая целевая операция")).toBeInTheDocument();
    expect(document.getElementById(`operation-${target.id}`)).toHaveAttribute(
      "data-state",
      "target",
    );
    expect(
      screen.getByText(
        "Операция открыта по прямой ссылке и не входит в текущую выборку.",
      ),
    ).toBeVisible();
  });

  it("moves the working state to the row whose action the user chooses", async () => {
    const user = userEvent.setup();
    const page = ledger();
    const originalOperation = required(page.items.at(0), "fixture operation");
    const firstOperation = deletableOperation(originalOperation);
    const secondOperation = deletableOperation({
      ...originalOperation,
      id: crypto.randomUUID(),
      description: "Вторая операция",
    });
    page.items = [firstOperation, secondOperation];
    page.pagination.total = 2;

    render(
      <MemoryRouter initialEntries={["/app/operations"]}>
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    const firstRow = required(
      document.getElementById(`operation-${firstOperation.id}`),
      "first operation row",
    );
    const secondRow = required(
      document.getElementById(`operation-${secondOperation.id}`),
      "second operation row",
    );
    const moreActions = screen.getAllByText("Ещё действия");
    await user.click(required(moreActions.at(0), "first more actions"));
    await user.click(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    );
    expect(firstRow).toHaveAttribute("data-state", "working");
    expect(secondRow).toHaveAttribute("data-state", "default");

    await user.click(required(moreActions.at(1), "second more actions"));
    await user.click(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    );
    expect(firstRow).toHaveAttribute("data-state", "default");
    expect(secondRow).toHaveAttribute("data-state", "working");
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
      <MemoryRouter initialEntries={["/app/operations"]}>
        <ManualLedgerPage ledger={page} session={session} />
      </MemoryRouter>,
    );

    await user.click(screen.getByText("Ещё действия"));
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
        editKind: "none" as const,
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
    canViewRawImportData: true,
    canViewMemberDirectory: true,
    canManageMembers: true,
    canViewWorkspaceActivity: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};

function ledger(): OperationsDto {
  const operationId = crypto.randomUUID();
  return {
    items: [
      {
        id: operationId,
        version: 3,
        operationType: "expense",
        source: "manual",
        operationDate: "2026-07-20",
        description: "Аренда за июль",
        status: "confirmed",
        money: {
          amount: "65000.00",
          currency: "RUB",
        },
        account: {
          id: crypto.randomUUID(),
          name: "Основной счёт",
          currency: "RUB",
        },
        sourceAccount: null,
        destinationAccount: null,
        category: null,
        property: null,
        provenance: null,
        capabilities: {
          canEdit: true,
          editKind: "manual",
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
        {
          id: crypto.randomUUID(),
          name: "Основной счёт",
          currency: "RUB",
          canRecordIncome: true,
          canRecordExpense: true,
          canTransfer: true,
        },
      ],
      categories: [],
      properties: [],
      sources: ["manual", "bank_pdf", "debt", "system"],
      perPage: [25, 50, 100, 200],
    },
    capabilities: { canCreate: true, readonlyReason: null },
    targetOperationId: null,
  };
}

function deletableOperation(
  operation: OperationsDto["items"][number],
): OperationsDto["items"][number] {
  return {
    ...operation,
    status: "ignored",
    capabilities: {
      canEdit: false,
      editKind: "none",
      canCancel: false,
      canRestore: false,
      canDelete: true,
      readonlyReason: null,
    },
  };
}

function required<T>(value: T | null | undefined, name: string): T {
  if (value === null || value === undefined) {
    throw new Error(`Test fixture requires ${name}.`);
  }
  return value;
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location-search">{location.search}</output>;
}
