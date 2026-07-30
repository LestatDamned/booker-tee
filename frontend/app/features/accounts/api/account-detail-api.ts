import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import {
  parseApiError,
  requestJson,
  type ApiErrorDetails,
} from "../../../api/transport";

export type AccountDetailDto =
  components["schemas"]["AccountDetailApiResponse"];

const namedReferenceSchema = z.object({ id: z.uuid(), name: z.string() });

export const accountMovementSchema = z.object({
  operationId: z.uuid(),
  version: z.number().int(),
  operationType: z.enum(["income", "expense", "transfer", "adjustment"]),
  operationDate: z.iso.date(),
  description: z.string(),
  status: z.enum([
    "draft",
    "needs_review",
    "confirmed",
    "ignored",
    "duplicate",
  ]),
  source: z.enum(["manual", "bank_pdf", "system"]),
  amount: z.string(),
  currency: z.string(),
  category: namedReferenceSchema.nullable(),
  property: namedReferenceSchema.nullable(),
  transferRoute: z.string().nullable(),
  sourceTarget: z.object({
    kind: z.enum(["manual", "import", "system"]),
    uploadedDocumentId: z.uuid().nullable(),
    rawTransactionId: z.uuid().nullable(),
  }),
  capabilities: z.object({
    canEditReviewFields: z.boolean(),
    readonlyReasonCode: z
      .enum([
        "financial_write_forbidden",
        "imported_operation_only",
        "operation_not_confirmed",
      ])
      .nullable(),
  }),
});

export const accountDetailSchema: z.ZodType<AccountDetailDto> = z.object({
  account: z.object({
    id: z.uuid(),
    name: z.string(),
    accountType: z.enum(["cash", "card", "deposit", "checking", "other"]),
    currency: z.string(),
    initialBalance: z.string(),
    balance: z.string(),
    isActive: z.boolean(),
    updatedAt: z.iso.datetime({ offset: true }),
    capabilities: z.object({
      canUpdate: z.boolean(),
      canArchive: z.boolean(),
      canRestore: z.boolean(),
    }),
  }),
  items: z.array(accountMovementSchema),
  pagination: z.object({
    page: z.number().int(),
    perPage: z.number().int(),
    total: z.number().int(),
    totalPages: z.number().int(),
    hasPrevious: z.boolean(),
    hasNext: z.boolean(),
  }),
  filterOptions: z.object({
    categories: z.array(namedReferenceSchema),
    properties: z.array(namedReferenceSchema),
    perPage: z.array(z.number().int()),
  }),
});

export type AccountDetailLoadResult =
  | { status: "success"; detail: AccountDetailDto }
  | { status: "unauthenticated" }
  | { status: "not_found" }
  | { status: "error"; message: string };

export type ImportedOperationCorrectionDraft = {
  categoryId: string | null;
  description: string;
  expectedVersion: number;
  propertyId: string | null;
};

export type ImportedOperationCorrectionResult =
  | { status: "success"; movement: AccountDetailDto["items"][number] }
  | { status: "unauthenticated" }
  | { status: "forbidden"; message: string }
  | { status: "conflict"; code: string; message: string }
  | ({ status: "error" } & ApiErrorDetails);

export async function loadAccountDetail(
  accountId: string,
  search: string,
  signal?: AbortSignal,
): Promise<AccountDetailLoadResult> {
  const response = await requestJson(`/api/v1/accounts/${accountId}${search}`, {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) {
    return {
      status: "error",
      message: `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = accountDetailSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", detail: parsed.data }
    : {
        status: "error",
        message: "API вернул проводки счёта неожиданного формата.",
      };
}

export async function updateImportedOperationReviewFields({
  accountId,
  csrfToken,
  draft,
  operationId,
}: {
  accountId: string;
  csrfToken: string;
  draft: ImportedOperationCorrectionDraft;
  operationId: string;
}): Promise<ImportedOperationCorrectionResult> {
  const response = await requestJson(
    `/api/v1/accounts/${accountId}/operations/${operationId}/review-fields`,
    {
      body: JSON.stringify(draft),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "PUT",
    },
  );
  if (response.status === "network_error") {
    return {
      status: "error",
      code: "network_error",
      fieldErrors: {},
      message: "Backend недоступен. Проверьте соединение и повторите.",
    };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  const apiError = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return {
      status: "forbidden",
      message: apiError?.message ?? "Исправление операции недоступно.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      code: apiError?.code ?? "operation_version_conflict",
      message: apiError?.message ?? "Операция уже изменилась.",
    };
  }
  if (!response.ok) {
    return {
      status: "error",
      code: apiError?.code ?? "operation_correction_failed",
      fieldErrors: apiError?.fieldErrors ?? {},
      message: apiError?.message ?? "Не удалось сохранить исправления.",
    };
  }
  const parsed = accountMovementSchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      code: "invalid_movement_response",
      fieldErrors: {},
      message: "API вернул операцию неожиданного формата.",
    };
  }
  return { status: "success", movement: parsed.data };
}
