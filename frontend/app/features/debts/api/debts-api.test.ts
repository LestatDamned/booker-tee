import { afterEach, describe, expect, it, vi } from "vitest";

import {
  changeDebtLifecycle,
  createDebt,
  deleteDebt,
  loadDebtDetail,
  loadDebts,
  recordDebtPayment,
  undoDebtPayment,
  updateDebt,
} from "./debts-api";

describe("debts API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("validates portfolio and detail responses at the network boundary", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(portfolioPayload))
      .mockResolvedValueOnce(jsonResponse(detailPayload));
    vi.stubGlobal("fetch", fetchMock);

    const portfolio = await loadDebts();
    const detail = await loadDebtDetail(DEBT_ID, 2, 10);

    expect(portfolio).toEqual({
      status: "success",
      portfolio: portfolioPayload,
    });
    expect(detail).toEqual({ status: "success", detail: detailPayload });
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      `/api/v1/debts/${DEBT_ID}?paymentsPage=2&paymentsPageSize=10`,
    );
  });

  it("rejects a malformed portfolio", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(jsonResponse({ ...portfolioPayload, totals: [{}] })),
      ),
    );

    await expect(loadDebts()).resolves.toEqual({
      status: "error",
      message: "API вернул список долгов неожиданного формата.",
    });
  });

  it("sends create and payment idempotency keys", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(detailPayload, 201)),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createDebt(
      {
        action: "give_loan",
        amount: "100.00",
        currency: "RUB",
        fundingAccountId: ACCOUNT_ID,
        name: "Займ Ивану",
        operationDate: "2026-08-09",
      },
      "csrf",
      "create-key",
    );
    await recordDebtPayment(
      DEBT_ID,
      {
        interestAmount: "10.00",
        operationDate: "2026-08-09",
        principalAmount: "25.00",
        settlementAccountId: ACCOUNT_ID,
      },
      "csrf",
      "payment-key",
    );

    expect(request(fetchMock, 0)).toMatchObject({
      url: "/api/v1/debts",
      headers: { "Idempotency-Key": "create-key", "X-CSRF-Token": "csrf" },
    });
    expect(request(fetchMock, 1)).toMatchObject({
      url: `/api/v1/debts/${DEBT_ID}/payments`,
      headers: { "Idempotency-Key": "payment-key" },
    });
  });

  it("uses server snapshots for lifecycle and undo", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(detailPayload)));
    vi.stubGlobal("fetch", fetchMock);

    await changeDebtLifecycle(detailPayload.debt, "archive", "csrf");
    await undoDebtPayment(detailPayload.payments.items[0]!, "csrf");

    expect(request(fetchMock, 0)).toMatchObject({
      url: `/api/v1/debts/${DEBT_ID}/archive`,
      body: {
        expectedActive: true,
        expectedUpdatedAt: "2026-08-09T12:00:00Z",
      },
    });
    expect(request(fetchMock, 1)).toMatchObject({
      url: `/api/v1/debt-payments/${PAYMENT_ID}/undo`,
      body: {
        expectedInterestOperationVersion: 2,
        expectedPrincipalOperationVersion: 1,
      },
    });
  });

  it("uses server snapshots for safe update and delete", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(detailPayload))
      .mockResolvedValueOnce(
        jsonResponse({ deletedId: DEBT_ID, name: "Кредит" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await updateDebt(
      DEBT_ID,
      {
        creditLimit: null,
        expectedUpdatedAt: debt.updatedAt,
        maturityDate: debt.maturityDate,
        name: "Кредит на ремонт",
        notes: "Уточнено",
        openedOn: debt.openedOn,
      },
      "csrf",
    );
    await deleteDebt(debt, "csrf");

    expect(request(fetchMock, 0)).toMatchObject({
      url: `/api/v1/debts/${DEBT_ID}`,
      method: "PUT",
      body: { expectedUpdatedAt: debt.updatedAt, name: "Кредит на ремонт" },
    });
    expect(request(fetchMock, 1)).toMatchObject({
      url: `/api/v1/debts/${DEBT_ID}`,
      method: "DELETE",
      body: { expectedUpdatedAt: debt.updatedAt },
    });
  });

  it("keeps network and conflict failures distinct", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "debt_payment_conflict",
              message: "Платёж уже изменился.",
            },
          },
          409,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadDebts()).resolves.toEqual({
      status: "error",
      message: "Backend недоступен.",
    });
    await expect(
      undoDebtPayment(detailPayload.payments.items[0]!, "csrf"),
    ).resolves.toEqual({
      status: "conflict",
      message: "Платёж уже изменился.",
    });
  });
});

function request(fetchMock: ReturnType<typeof vi.fn>, index: number) {
  const [url, init] = fetchMock.mock.calls[index] as [string, RequestInit];
  return {
    body: JSON.parse(String(init.body)) as unknown,
    headers: init.headers,
    method: init.method,
    url,
  };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

const DEBT_ID = "11111111-1111-4111-8111-111111111111";
const ACCOUNT_ID = "22222222-2222-4222-8222-222222222222";
const PAYMENT_ID = "33333333-3333-4333-8333-333333333333";

const debt = {
  accountId: DEBT_ID,
  availableCredit: null,
  balance: "-75.00",
  capabilities: {
    canArchive: false,
    canDelete: false,
    canRecordPayment: true,
    canRestore: false,
    canUpdate: true,
    deleteBlockedReason: "financial_history" as const,
    paymentBlockedReason: null,
  },
  creditLimit: null,
  currency: "RUB",
  isActive: true,
  kind: "loan_payable" as const,
  maturityDate: "2027-01-01",
  name: "Кредит",
  openedOn: "2026-01-01",
  originalPrincipal: "100.00",
  outstanding: "75.00",
  status: "active" as const,
  updatedAt: "2026-08-09T12:00:00Z",
};

const payment = {
  canUndo: true,
  createdAt: "2026-08-09T12:00:00Z",
  interest: {
    amount: "10.00",
    description: "Проценты",
    operationDate: "2026-08-09",
    operationId: "55555555-5555-4555-8555-555555555555",
    operationType: "expense" as const,
    status: "confirmed" as const,
    version: 2,
  },
  notes: null,
  paymentId: PAYMENT_ID,
  principal: {
    amount: "25.00",
    description: "Платёж",
    operationDate: "2026-08-09",
    operationId: "44444444-4444-4444-8444-444444444444",
    operationType: "transfer" as const,
    status: "confirmed" as const,
    version: 1,
  },
  reversedAt: null,
};

const detailPayload = {
  debt,
  notes: "Тест",
  paymentTotals: { interest: "10.00", principal: "25.00" },
  payments: {
    hasNext: false,
    hasPrevious: false,
    items: [payment],
    page: 1,
    pageSize: 20,
    total: 1,
    totalPages: 1,
  },
};

const portfolioPayload = {
  capabilities: { canCreate: true, readonlyReasonCode: null },
  items: [debt],
  totals: [
    {
      currency: "RUB",
      netPosition: "-75.00",
      payable: "75.00",
      receivable: "0.00",
    },
  ],
};
