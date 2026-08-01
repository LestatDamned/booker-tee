import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import {
  parseApiError,
  requestJson,
  type ApiErrorDetails,
} from "../../../api/transport";

export type CategoryDirectoryDto =
  components["schemas"]["CategoryDirectoryApiResponse"];
export type CategorySummaryDto =
  components["schemas"]["CategorySummaryApiResponse"];
export type CategoryKind = components["schemas"]["CategoryKind"];

export const categoryKindSchema = z.enum([
  "income",
  "expense",
  "transfer",
  "adjustment",
  "mixed",
]);

export const categorySummarySchema: z.ZodType<CategorySummaryDto> = z.object({
  id: z.uuid(),
  name: z.string(),
  kind: categoryKindSchema,
  isActive: z.boolean(),
  isSystem: z.boolean(),
  systemKey: z.string().nullable(),
  notes: z.string().nullable(),
  operationCount: z.number().int().nonnegative(),
  ruleCount: z.number().int().nonnegative(),
  activeRuleCount: z.number().int().nonnegative(),
  deleteBlockers: z.object({
    operationCount: z.number().int().nonnegative(),
    ruleCount: z.number().int().nonnegative(),
    rawSuggestionCount: z.number().int().nonnegative(),
    childCategoryCount: z.number().int().nonnegative(),
    reasonCodes: z.array(
      z.enum([
        "active_category",
        "operations",
        "rules",
        "raw_suggestions",
        "child_categories",
      ]),
    ),
  }),
  updatedAt: z.iso.datetime({ offset: true }),
  capabilities: z.object({
    canUpdate: z.boolean(),
    canArchive: z.boolean(),
    canRestore: z.boolean(),
    canDelete: z.boolean(),
    archiveBlockedReasonCode: z.enum(["active_rules"]).nullable(),
  }),
});

const categoryDirectorySchema: z.ZodType<CategoryDirectoryDto> = z.object({
  items: z.array(categorySummarySchema),
  kindOptions: z.array(
    z.object({
      value: categoryKindSchema,
      label: z.string(),
      description: z.string(),
    }),
  ),
  capabilities: z.object({
    canCreate: z.boolean(),
    readonlyReasonCode: z.enum(["financial_write_forbidden"]).nullable(),
  }),
});

export type CategoryDirectoryLoadResult =
  | { status: "success"; directory: CategoryDirectoryDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export type CreateCategoryDraft = {
  name: string;
  kind: CategoryKind;
  notes: string;
};

export type CreateCategoryResult =
  | { status: "success"; category: CategorySummaryDto }
  | { status: "unauthenticated" }
  | { status: "forbidden"; message: string }
  | ({ status: "error" } & ApiErrorDetails);

export async function loadCategories(
  signal?: AbortSignal,
): Promise<CategoryDirectoryLoadResult> {
  const response = await requestJson("/api/v1/categories", {
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
  const parsed = categoryDirectorySchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      message: "API вернул список категорий неожиданного формата.",
    };
  }
  return { status: "success", directory: parsed.data };
}

export async function createCategory({
  csrfToken,
  draft,
}: {
  csrfToken: string;
  draft: CreateCategoryDraft;
}): Promise<CreateCategoryResult> {
  const response = await requestJson("/api/v1/categories", {
    body: JSON.stringify(draft),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    method: "POST",
  });
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
      message: apiError?.message ?? "Создание категории недоступно.",
    };
  }
  if (!response.ok) {
    return {
      status: "error",
      code: apiError?.code ?? "category_create_failed",
      fieldErrors: apiError?.fieldErrors ?? {},
      message: apiError?.message ?? "Не удалось создать категорию.",
    };
  }
  const parsed = categorySummarySchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      code: "invalid_category_response",
      fieldErrors: {},
      message: "API вернул созданную категорию неожиданного формата.",
    };
  }
  return { status: "success", category: parsed.data };
}
