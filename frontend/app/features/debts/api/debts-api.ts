import { z } from "zod";

import {
  apiForbiddenFailure,
  apiLoadError,
  apiLoadNetworkError,
  apiMutationError,
  apiMutationNetworkError,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
  type ApiForbiddenFailure,
  type ApiLoadError,
  type ApiMutationError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

export type DebtPortfolioDto =
  components["schemas"]["DebtPortfolioApiResponse"];
export type DebtDetailDto = components["schemas"]["DebtDetailApiResponse"];
export type DebtSummaryDto = components["schemas"]["DebtSummaryApiResponse"];
export type DebtKind = components["schemas"]["DebtKind"];
export type DebtCreateRequest =
  | components["schemas"]["AddExistingDebtApiRequest"]
  | components["schemas"]["GiveLoanApiRequest"]
  | components["schemas"]["TakeLoanApiRequest"]
  | components["schemas"]["OpenCreditCardApiRequest"];
export type DebtPaymentRequest =
  components["schemas"]["RecordDebtPaymentApiRequest"];
export type DebtUpdateRequest = components["schemas"]["UpdateDebtApiRequest"];

const debtKindSchema = z.enum([
  "loan_receivable",
  "loan_payable",
  "credit_card",
  "mortgage",
]);
const debtStatusSchema = z.enum(["active", "settled", "no_debt", "archived"]);
const paymentBlockedReasonSchema = z.enum([
  "financial_write_forbidden",
  "debt_archived",
  "debt_settled",
  "no_payment_account",
]);
const deleteBlockedReasonSchema = z.enum([
  "financial_write_forbidden",
  "financial_history",
]);
const operationSchema = z.object({
  operationId: z.uuid(),
  version: z.number().int().positive(),
  operationDate: z.iso.date(),
  operationType: z.enum(["income", "expense", "transfer", "adjustment"]),
  status: z.enum([
    "draft",
    "needs_review",
    "confirmed",
    "ignored",
    "duplicate",
  ]),
  description: z.string().nullable(),
  amount: z.string(),
});

export const debtSummarySchema: z.ZodType<DebtSummaryDto> = z.object({
  accountId: z.uuid(),
  name: z.string(),
  kind: debtKindSchema,
  currency: z.string(),
  balance: z.string(),
  outstanding: z.string(),
  status: debtStatusSchema,
  openedOn: z.iso.date().nullable(),
  originalPrincipal: z.string().nullable(),
  maturityDate: z.iso.date().nullable(),
  creditLimit: z.string().nullable(),
  availableCredit: z.string().nullable(),
  isActive: z.boolean(),
  updatedAt: z.iso.datetime({ offset: true }),
  capabilities: z.object({
    canRecordPayment: z.boolean(),
    canArchive: z.boolean(),
    canRestore: z.boolean(),
    canUpdate: z.boolean(),
    canDelete: z.boolean(),
    paymentBlockedReason: paymentBlockedReasonSchema.nullable(),
    deleteBlockedReason: deleteBlockedReasonSchema.nullable(),
  }),
});

export const debtPortfolioSchema: z.ZodType<DebtPortfolioDto> = z.object({
  items: z.array(debtSummarySchema),
  totals: z.array(
    z.object({
      currency: z.string(),
      receivable: z.string(),
      payable: z.string(),
      netPosition: z.string(),
    }),
  ),
  capabilities: z.object({
    canCreate: z.boolean(),
    readonlyReasonCode: z.literal("financial_write_forbidden").nullable(),
  }),
});

export const debtDetailSchema: z.ZodType<DebtDetailDto> = z.object({
  debt: debtSummarySchema,
  notes: z.string().nullable(),
  paymentTotals: z.object({ principal: z.string(), interest: z.string() }),
  payments: z.object({
    items: z.array(
      z.object({
        paymentId: z.uuid(),
        principal: operationSchema.nullable(),
        interest: operationSchema.nullable(),
        notes: z.string().nullable(),
        createdAt: z.iso.datetime({ offset: true }),
        reversedAt: z.iso.datetime({ offset: true }).nullable(),
        canUndo: z.boolean(),
      }),
    ),
    page: z.number().int().positive(),
    pageSize: z.number().int().positive(),
    total: z.number().int().nonnegative(),
    totalPages: z.number().int().nonnegative(),
    hasPrevious: z.boolean(),
    hasNext: z.boolean(),
  }),
});

export type DebtPortfolioLoadResult =
  | { status: "success"; portfolio: DebtPortfolioDto }
  | ApiUnauthenticatedFailure
  | ApiLoadError;
export type DebtDetailLoadResult =
  | { status: "success"; detail: DebtDetailDto }
  | ApiUnauthenticatedFailure
  | { status: "not_found" }
  | ApiLoadError;
export type DebtMutationResult =
  | { status: "success"; detail: DebtDetailDto }
  | ApiUnauthenticatedFailure
  | ApiForbiddenFailure
  | { status: "conflict"; message: string }
  | ApiMutationError;
export type DebtDeleteResult =
  | { status: "success"; deletedId: string; name: string }
  | ApiUnauthenticatedFailure
  | ApiForbiddenFailure
  | { status: "conflict"; message: string }
  | ApiMutationError;

export async function loadDebts(
  signal?: AbortSignal,
): Promise<DebtPortfolioLoadResult> {
  const response = await requestJson("/api/v1/debts", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = debtPortfolioSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", portfolio: parsed.data }
    : apiLoadError("API вернул список долгов неожиданного формата.");
}

export async function loadDebtDetail(
  debtId: string,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<DebtDetailLoadResult> {
  const params = new URLSearchParams({
    paymentsPage: String(page),
    paymentsPageSize: String(pageSize),
  });
  const response = await requestJson(`/api/v1/debts/${debtId}?${params}`, {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = debtDetailSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", detail: parsed.data }
    : apiLoadError("API вернул карточку долга неожиданного формата.");
}

export async function createDebt(
  request: DebtCreateRequest,
  csrfToken: string,
  idempotencyKey: string,
): Promise<DebtMutationResult> {
  return debtMutation(
    "/api/v1/debts",
    request,
    csrfToken,
    "Не удалось добавить долг.",
    idempotencyKey,
  );
}

export async function recordDebtPayment(
  debtId: string,
  request: DebtPaymentRequest,
  csrfToken: string,
  idempotencyKey: string,
): Promise<DebtMutationResult> {
  return debtMutation(
    `/api/v1/debts/${debtId}/payments`,
    request,
    csrfToken,
    "Не удалось записать платёж.",
    idempotencyKey,
  );
}

export async function changeDebtLifecycle(
  debt: Pick<DebtSummaryDto, "accountId" | "isActive" | "updatedAt">,
  action: "archive" | "restore",
  csrfToken: string,
): Promise<DebtMutationResult> {
  return debtMutation(
    `/api/v1/debts/${debt.accountId}/${action}`,
    { expectedActive: debt.isActive, expectedUpdatedAt: debt.updatedAt },
    csrfToken,
    "Не удалось изменить состояние долга.",
  );
}

export async function updateDebt(
  debtId: string,
  request: DebtUpdateRequest,
  csrfToken: string,
): Promise<DebtMutationResult> {
  return debtMutation(
    `/api/v1/debts/${debtId}`,
    request,
    csrfToken,
    "Не удалось изменить долг.",
    undefined,
    "PUT",
  );
}

export async function deleteDebt(
  debt: Pick<DebtSummaryDto, "accountId" | "updatedAt">,
  csrfToken: string,
): Promise<DebtDeleteResult> {
  const response = await requestJson(`/api/v1/debts/${debt.accountId}`, {
    body: JSON.stringify({ expectedUpdatedAt: debt.updatedAt }),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    method: "DELETE",
  });
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return apiForbiddenFailure(error, "Удаление долга недоступно.");
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: error?.message ?? "Долг уже изменился. Обновите страницу.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "debt_delete_failed",
      fallbackMessage: "Не удалось удалить долг.",
    });
  }
  const parsed = z
    .object({ deletedId: z.uuid(), name: z.string() })
    .safeParse(response.body);
  return parsed.success
    ? { status: "success", ...parsed.data }
    : apiMutationError(null, {
        fallbackCode: "invalid_debt_delete_response",
        fallbackMessage: "API вернул неожиданный результат удаления.",
      });
}

export async function undoDebtPayment(
  payment: DebtDetailDto["payments"]["items"][number],
  csrfToken: string,
): Promise<DebtMutationResult> {
  return debtMutation(
    `/api/v1/debt-payments/${payment.paymentId}/undo`,
    {
      expectedPrincipalOperationVersion: payment.principal?.version ?? null,
      expectedInterestOperationVersion: payment.interest?.version ?? null,
    },
    csrfToken,
    "Не удалось отменить платёж.",
  );
}

async function debtMutation(
  url: string,
  body: unknown,
  csrfToken: string,
  fallbackMessage: string,
  idempotencyKey?: string,
  method: "POST" | "PUT" = "POST",
): Promise<DebtMutationResult> {
  const response = await requestJson(url, {
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
      "X-CSRF-Token": csrfToken,
    },
    method,
  });
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return apiForbiddenFailure(error, "Финансовое действие недоступно.");
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: error?.message ?? "Долг уже изменился. Обновите страницу.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "debt_mutation_failed",
      fallbackMessage,
    });
  }
  const parsed = debtDetailSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", detail: parsed.data }
    : apiMutationError(null, {
        fallbackCode: "invalid_debt_response",
        fallbackMessage: "API вернул долг неожиданного формата.",
      });
}
