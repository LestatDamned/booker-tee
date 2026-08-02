import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

export type TransactionRuleDirectoryDto =
  components["schemas"]["TransactionRuleDirectoryApiResponse"];
export type TransactionRuleSummaryDto =
  components["schemas"]["TransactionRuleSummaryApiResponse"];
export type TransactionRuleDirectoryStatus =
  components["schemas"]["TransactionRuleDirectoryStatus"];
export type TransactionRuleCreateRequest =
  components["schemas"]["TransactionRuleCreateApiRequest"];
export type TransactionRuleUpdateRequest =
  components["schemas"]["TransactionRuleUpdateApiRequest"];
export type TransactionRuleEditDto =
  components["schemas"]["TransactionRuleEditApiResponse"];
export type TransactionRuleLifecycleDto =
  components["schemas"]["TransactionRuleLifecycleApiResponse"];
export type TransactionRuleSeedDefaultsDto =
  components["schemas"]["TransactionRuleSeedDefaultsApiResponse"];

const referenceSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  isActive: z.boolean(),
});

const summarySchema: z.ZodType<TransactionRuleSummaryDto> = z.object({
  id: z.uuid(),
  name: z.string(),
  priority: z.number().int(),
  isActive: z.boolean(),
  updatedAt: z.iso.datetime({ offset: true }),
  condition: z.object({
    pattern: z.string(),
    matchType: z.enum(["contains", "exact"]),
    direction: z.enum(["inflow", "outflow", "any"]),
    account: referenceSchema.nullable(),
    amountMin: z.string().nullable(),
    amountMax: z.string().nullable(),
  }),
  outcome: z.object({
    operationType: z
      .enum(["income", "expense", "transfer", "adjustment"])
      .nullable(),
    category: referenceSchema.nullable(),
    property: referenceSchema.nullable(),
    applicationMode: z.enum(["suggest", "auto_apply"]),
    autoDescription: z.string().nullable(),
    affectsProfit: z.boolean().nullable(),
  }),
  usage: z.object({
    directRawSuggestionCount: z.number().int().nonnegative(),
  }),
  capabilities: z.object({
    canUpdate: z.boolean(),
    canEnable: z.boolean(),
    canDisable: z.boolean(),
    canDelete: z.boolean(),
    enableBlockedReasonCode: z
      .enum(["category_inactive", "property_archived", "account_unavailable"])
      .nullable(),
    deleteBlockedReasonCode: z
      .enum(["active_rule", "raw_suggestions"])
      .nullable(),
  }),
});

const directorySchema: z.ZodType<TransactionRuleDirectoryDto> = z.object({
  items: z.array(summarySchema),
  page: z.object({
    page: z.number().int().positive(),
    pageSize: z.number().int().positive(),
    total: z.number().int().nonnegative(),
    totalPages: z.number().int().positive(),
    hasPrevious: z.boolean(),
    hasNext: z.boolean(),
  }),
  counts: z.object({
    all: z.number().int().nonnegative(),
    active: z.number().int().nonnegative(),
    disabled: z.number().int().nonnegative(),
  }),
  appliedFilters: z.object({
    q: z.string().nullable(),
    categoryId: z.uuid().nullable(),
    status: z.enum(["all", "active", "disabled"]),
  }),
  references: z.object({
    categories: z.array(referenceSchema),
    properties: z.array(referenceSchema),
  }),
  capabilities: z.object({
    canCreate: z.boolean(),
    canSeedDefaults: z.boolean(),
    readonlyReasonCode: z.enum(["financial_write_forbidden"]).nullable(),
  }),
});

const createResponseSchema = z.object({
  item: summarySchema,
  replayed: z.boolean(),
});

const editResponseSchema: z.ZodType<TransactionRuleEditDto> = z.object({
  item: summarySchema,
  references: z.object({
    categories: z.array(referenceSchema),
    properties: z.array(referenceSchema),
  }),
});

const seedResponseSchema: z.ZodType<TransactionRuleSeedDefaultsDto> = z.object({
  createdRules: z.number().int().nonnegative(),
  existingRules: z.number().int().nonnegative(),
  createdCategories: z.number().int().nonnegative(),
});

const lifecycleResponseSchema: z.ZodType<TransactionRuleLifecycleDto> =
  z.object({
    item: summarySchema,
    impact: z.object({
      futureMatchingChanged: z.boolean(),
      existingSuggestionsChanged: z.boolean(),
      existingSuggestionCount: z.number().int().nonnegative(),
    }),
  });

export type TransactionRuleMutationResult<T> =
  | { status: "success"; value: T }
  | {
      status: "validation_error";
      fieldErrors: Record<string, string[]>;
      message: string;
    }
  | { status: "conflict"; message: string }
  | { status: "forbidden"; message: string }
  | { status: "error"; message: string };

export type TransactionRuleDirectoryLoadResult =
  | { status: "success"; directory: TransactionRuleDirectoryDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export type TransactionRuleLifecycleResult =
  | { status: "success"; value: TransactionRuleLifecycleDto }
  | {
      status: "blocked";
      blockedReasonCode: string | null;
      message: string;
    }
  | { status: "conflict"; message: string }
  | { status: "forbidden"; message: string }
  | { status: "error"; message: string };

export async function loadTransactionRules(
  search: string,
  signal?: AbortSignal,
): Promise<TransactionRuleDirectoryLoadResult> {
  const response = await requestJson(`/api/v1/transaction-rules${search}`, {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    return {
      status: "error",
      message: `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = directorySchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      message: "API вернул список правил неожиданного формата.",
    };
  }
  return { status: "success", directory: parsed.data };
}

export async function createTransactionRule(
  request: TransactionRuleCreateRequest,
  options: { csrfToken: string; idempotencyKey: string },
): Promise<
  TransactionRuleMutationResult<{
    item: TransactionRuleSummaryDto;
    replayed: boolean;
  }>
> {
  const response = await requestJson("/api/v1/transaction-rules", {
    body: JSON.stringify(request),
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": options.idempotencyKey,
      "X-CSRF-Token": options.csrfToken,
    },
    method: "POST",
  });
  return mutationResult(response, createResponseSchema);
}

export async function seedDefaultTransactionRules(
  csrfToken: string,
): Promise<TransactionRuleMutationResult<TransactionRuleSeedDefaultsDto>> {
  const response = await requestJson(
    "/api/v1/transaction-rules/seed-defaults",
    {
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
  return mutationResult(response, seedResponseSchema);
}

export async function loadTransactionRuleForEdit(
  ruleId: string,
): Promise<TransactionRuleMutationResult<TransactionRuleEditDto>> {
  const response = await requestJson(
    `/api/v1/transaction-rules/${ruleId}/edit`,
  );
  return mutationResult(response, editResponseSchema);
}

export async function updateTransactionRule(
  ruleId: string,
  request: TransactionRuleUpdateRequest,
  csrfToken: string,
): Promise<TransactionRuleMutationResult<TransactionRuleSummaryDto>> {
  const response = await requestJson(`/api/v1/transaction-rules/${ruleId}`, {
    body: JSON.stringify(request),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    method: "PUT",
  });
  return mutationResult(response, summarySchema);
}

export async function changeTransactionRuleLifecycle(
  item: TransactionRuleSummaryDto,
  action: "enable" | "disable",
  csrfToken: string,
): Promise<TransactionRuleLifecycleResult> {
  const response = await requestJson(
    `/api/v1/transaction-rules/${item.id}/${action}`,
    {
      body: JSON.stringify({
        expectedActive: item.isActive,
        expectedUpdatedAt: item.updatedAt,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
    },
  );
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.ok) {
    const parsed = lifecycleResponseSchema.safeParse(response.body);
    return parsed.success
      ? { status: "success", value: parsed.data }
      : { status: "error", message: "API вернул неожиданный ответ." };
  }
  const error = parseApiError(response.body);
  const message = error?.message ?? `API вернул статус ${response.httpStatus}.`;
  if (
    response.httpStatus === 422 &&
    error?.code === "transaction_rule_activation_blocked"
  ) {
    const reason = error.details?.blockedReasonCode;
    return {
      status: "blocked",
      blockedReasonCode: typeof reason === "string" ? reason : null,
      message,
    };
  }
  if (response.httpStatus === 409) return { status: "conflict", message };
  if (response.httpStatus === 401 || response.httpStatus === 403) {
    return { status: "forbidden", message };
  }
  return { status: "error", message };
}

function mutationResult<T>(
  response: Awaited<ReturnType<typeof requestJson>>,
  schema: z.ZodType<T>,
): TransactionRuleMutationResult<T> {
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.ok) {
    const parsed = schema.safeParse(response.body);
    return parsed.success
      ? { status: "success", value: parsed.data }
      : { status: "error", message: "API вернул неожиданный ответ." };
  }
  const error = parseApiError(response.body);
  const message = error?.message ?? `API вернул статус ${response.httpStatus}.`;
  if (response.httpStatus === 422) {
    return {
      status: "validation_error",
      fieldErrors: error?.fieldErrors ?? {},
      message,
    };
  }
  if (response.httpStatus === 409) return { status: "conflict", message };
  if (response.httpStatus === 401 || response.httpStatus === 403) {
    return { status: "forbidden", message };
  }
  return { status: "error", message };
}
