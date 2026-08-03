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
  | ApiUnauthenticatedFailure
  | ApiLoadError;

export type CreateCategoryDraft = {
  name: string;
  kind: CategoryKind;
  notes: string;
};

export type CreateCategoryResult =
  | { status: "success"; category: CategorySummaryDto }
  | ApiUnauthenticatedFailure
  | ApiForbiddenFailure
  | ApiMutationError;

export async function loadCategories(
  signal?: AbortSignal,
): Promise<CategoryDirectoryLoadResult> {
  const response = await requestJson("/api/v1/categories", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return apiLoadNetworkError();
  }
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (!response.ok) {
    return apiUnexpectedStatusError(response.httpStatus);
  }
  const parsed = categoryDirectorySchema.safeParse(response.body);
  if (!parsed.success) {
    return apiLoadError("API вернул список категорий неожиданного формата.");
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
    return apiMutationNetworkError();
  }
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const apiError = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return apiForbiddenFailure(apiError, "Создание категории недоступно.");
  }
  if (!response.ok) {
    return apiMutationError(apiError, {
      fallbackCode: "category_create_failed",
      fallbackMessage: "Не удалось создать категорию.",
    });
  }
  const parsed = categorySummarySchema.safeParse(response.body);
  if (!parsed.success) {
    return apiMutationError(null, {
      fallbackCode: "invalid_category_response",
      fallbackMessage: "API вернул созданную категорию неожиданного формата.",
    });
  }
  return { status: "success", category: parsed.data };
}
