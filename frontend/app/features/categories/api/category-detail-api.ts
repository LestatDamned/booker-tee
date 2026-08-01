import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import {
  parseApiError,
  requestJson,
  type ApiErrorDetails,
} from "../../../api/transport";
import {
  categoryKindSchema,
  categorySummarySchema,
  type CategoryKind,
} from "./categories-api";

export type CategoryDetailDto =
  components["schemas"]["CategoryDetailApiResponse"];
export type CategoryLifecycleAction = "archive" | "restore";
export type CategoryLifecycleImpactDto =
  components["schemas"]["CategoryLifecycleImpactApiResponse"];

const operationTypeSchema = z.enum([
  "income",
  "expense",
  "transfer",
  "adjustment",
]);

export const categoryDetailSchema: z.ZodType<CategoryDetailDto> = z.object({
  category: categorySummarySchema,
  kindOptions: z.array(
    z.object({
      value: categoryKindSchema,
      label: z.string(),
      description: z.string(),
    }),
  ),
  kindChangeImpact: z.object({
    existingOperationsUnchanged: z.boolean(),
    pickerCompatibilityMayChange: z.boolean(),
    operationCount: z.number().int().nonnegative(),
    ruleCount: z.number().int().nonnegative(),
    requiresConfirmation: z.boolean(),
  }),
  appliedFilters: z.object({
    dateFrom: z.iso.date().nullable(),
    dateTo: z.iso.date().nullable(),
    currency: z.string().length(3),
    operationType: operationTypeSchema.nullable(),
    search: z.string().nullable(),
  }),
  availableCurrencies: z.array(z.string().length(3)),
  summary: z.object({
    currency: z.string().length(3),
    income: z.string(),
    expense: z.string(),
    profit: z.string(),
  }),
  operations: z.object({
    items: z.array(
      z.object({
        operationId: z.uuid(),
        operationDate: z.iso.date(),
        operationType: operationTypeSchema,
        description: z.string(),
        accountName: z.string(),
        propertyId: z.uuid().nullable(),
        propertyName: z.string().nullable(),
        signedAmount: z.string(),
        currency: z.string().length(3),
      }),
    ),
    page: z.number().int().positive(),
    pageSize: z.number().int().positive().max(100),
    total: z.number().int().nonnegative(),
    totalPages: z.number().int().positive(),
    hasPrevious: z.boolean(),
    hasNext: z.boolean(),
  }),
  rules: z.object({
    items: z.array(
      z.object({
        id: z.uuid(),
        name: z.string(),
        isActive: z.boolean(),
        priority: z.number().int(),
        pattern: z.string(),
        matchType: z.enum(["contains", "exact"]),
        applicationMode: z.enum(["suggest", "auto_apply"]),
      }),
    ),
    total: z.number().int().nonnegative(),
    activeCount: z.number().int().nonnegative(),
  }),
});

export type CategoryDetailLoadResult =
  | { status: "success"; detail: CategoryDetailDto }
  | { status: "unauthenticated" }
  | { status: "not_found" }
  | { status: "error"; message: string };

export type UpdateCategoryDraft = {
  name: string;
  kind: CategoryKind;
  notes: string;
};

export type UpdateCategoryResult =
  | { status: "success"; detail: CategoryDetailDto }
  | { status: "unauthenticated" }
  | { status: "forbidden"; message: string }
  | { status: "not_found"; message: string }
  | { status: "conflict"; message: string }
  | ({ status: "error" } & ApiErrorDetails);

export type CategoryLifecycleResult =
  | {
      status: "success";
      category: CategoryDetailDto["category"];
      impact: CategoryLifecycleImpactDto;
    }
  | { status: "unauthenticated" }
  | {
      status: "forbidden" | "not_found" | "conflict" | "blocked";
      message: string;
    }
  | ({ status: "error" } & ApiErrorDetails);

export type CategoryDeleteResult =
  | { status: "success"; deletedId: string; name: string }
  | { status: "unauthenticated" }
  | {
      status: "forbidden" | "not_found" | "conflict" | "blocked";
      message: string;
    }
  | ({ status: "error" } & ApiErrorDetails);

const categoryLifecycleResponseSchema = z.object({
  category: categorySummarySchema,
  impact: z.object({
    historyPreserved: z.boolean(),
    rulesUnchanged: z.boolean(),
    availableForNewReferences: z.boolean(),
  }),
});

const categoryDeleteResponseSchema = z.object({
  deletedId: z.uuid(),
  name: z.string(),
});

export async function loadCategoryDetail(
  categoryId: string,
  search: string,
  signal?: AbortSignal,
): Promise<CategoryDetailLoadResult> {
  const response = await requestJson(
    `/api/v1/categories/${categoryId}${search}`,
    { ...(signal ? { signal } : {}) },
  );
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
  const parsed = categoryDetailSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", detail: parsed.data }
    : {
        status: "error",
        message: "API вернул detail категории неожиданного формата.",
      };
}

export async function updateCategory({
  categoryId,
  csrfToken,
  draft,
  expectedUpdatedAt,
  search,
}: {
  categoryId: string;
  csrfToken: string;
  draft: UpdateCategoryDraft;
  expectedUpdatedAt: string;
  search: string;
}): Promise<UpdateCategoryResult> {
  const response = await requestJson(
    `/api/v1/categories/${categoryId}${search}`,
    {
      body: JSON.stringify({ ...draft, expectedUpdatedAt }),
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
      message: apiError?.message ?? "Изменение категории недоступно.",
    };
  }
  if (response.httpStatus === 404) {
    return {
      status: "not_found",
      message: apiError?.message ?? "Категория не найдена.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: apiError?.message ?? "Категория уже изменена. Обновите данные.",
    };
  }
  if (!response.ok) {
    return {
      status: "error",
      code: apiError?.code ?? "category_update_failed",
      fieldErrors: apiError?.fieldErrors ?? {},
      message: apiError?.message ?? "Не удалось изменить категорию.",
    };
  }
  const parsed = categoryDetailSchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      code: "invalid_category_detail_response",
      fieldErrors: {},
      message: "API вернул изменённую категорию неожиданного формата.",
    };
  }
  return { status: "success", detail: parsed.data };
}

export async function changeCategoryLifecycle({
  action,
  category,
  csrfToken,
}: {
  action: CategoryLifecycleAction;
  category: Pick<
    CategoryDetailDto["category"],
    "id" | "isActive" | "updatedAt"
  >;
  csrfToken: string;
}): Promise<CategoryLifecycleResult> {
  const response = await requestJson(
    `/api/v1/categories/${category.id}/${action}`,
    {
      body: JSON.stringify({
        expectedStatus: category.isActive,
        expectedUpdatedAt: category.updatedAt,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
    },
  );
  if (response.status === "network_error") {
    return categoryMutationNetworkError();
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  const apiError = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return mutationFailure(
      "forbidden",
      apiError,
      "Изменение категории недоступно.",
    );
  }
  if (response.httpStatus === 404) {
    return mutationFailure("not_found", apiError, "Категория не найдена.");
  }
  if (response.httpStatus === 409) {
    return mutationFailure("conflict", apiError, "Категория уже изменена.");
  }
  if (
    response.httpStatus === 422 &&
    apiError?.code === "category_archive_blocked"
  ) {
    return mutationFailure(
      "blocked",
      apiError,
      "Сначала отключите активные правила категории.",
    );
  }
  if (!response.ok) {
    return categoryMutationError(
      apiError,
      "Не удалось изменить состояние категории.",
    );
  }
  const parsed = categoryLifecycleResponseSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", ...parsed.data }
    : categoryMutationError(
        null,
        "API вернул состояние категории неожиданного формата.",
      );
}

export async function deleteCategory({
  category,
  csrfToken,
}: {
  category: Pick<
    CategoryDetailDto["category"],
    "id" | "isActive" | "updatedAt"
  >;
  csrfToken: string;
}): Promise<CategoryDeleteResult> {
  const response = await requestJson(`/api/v1/categories/${category.id}`, {
    body: JSON.stringify({
      expectedStatus: category.isActive,
      expectedUpdatedAt: category.updatedAt,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    method: "DELETE",
  });
  if (response.status === "network_error")
    return categoryMutationNetworkError();
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  const apiError = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return mutationFailure(
      "forbidden",
      apiError,
      "Удаление категории недоступно.",
    );
  }
  if (response.httpStatus === 404) {
    return mutationFailure("not_found", apiError, "Категория не найдена.");
  }
  if (response.httpStatus === 409) {
    return mutationFailure("conflict", apiError, "Категория уже изменена.");
  }
  if (
    response.httpStatus === 422 &&
    apiError?.code === "category_delete_blocked"
  ) {
    return mutationFailure(
      "blocked",
      apiError,
      "Категория используется и не может быть удалена.",
    );
  }
  if (!response.ok) {
    return categoryMutationError(apiError, "Не удалось удалить категорию.");
  }
  const parsed = categoryDeleteResponseSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", ...parsed.data }
    : categoryMutationError(
        null,
        "API вернул результат удаления неожиданного формата.",
      );
}

function categoryMutationNetworkError() {
  return {
    status: "error" as const,
    code: "network_error",
    fieldErrors: {},
    message: "Backend недоступен. Проверьте соединение и повторите.",
  };
}

function mutationFailure<
  Status extends "forbidden" | "not_found" | "conflict" | "blocked",
>(status: Status, error: ApiErrorDetails | null, fallback: string) {
  return { status, message: error?.message ?? fallback };
}

function categoryMutationError(
  error: ApiErrorDetails | null,
  fallback: string,
) {
  return {
    status: "error" as const,
    code: error?.code ?? "category_mutation_failed",
    ...(error?.details ? { details: error.details } : {}),
    fieldErrors: error?.fieldErrors ?? {},
    message: error?.message ?? fallback,
  };
}
