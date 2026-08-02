import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { requestJson } from "../../../api/transport";

export type TransactionRuleDirectoryDto =
  components["schemas"]["TransactionRuleDirectoryApiResponse"];
export type TransactionRuleSummaryDto =
  components["schemas"]["TransactionRuleSummaryApiResponse"];
export type TransactionRuleDirectoryStatus =
  components["schemas"]["TransactionRuleDirectoryStatus"];

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

export type TransactionRuleDirectoryLoadResult =
  | { status: "success"; directory: TransactionRuleDirectoryDto }
  | { status: "unauthenticated" }
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
