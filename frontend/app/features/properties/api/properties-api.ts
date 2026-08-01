import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import {
  parseApiError,
  requestJson,
  type ApiErrorDetails,
} from "../../../api/transport";

export type PropertyDirectoryDto =
  components["schemas"]["PropertyDirectoryApiResponse"];
export type PropertySummaryDto =
  components["schemas"]["PropertySummaryApiResponse"];
export type PropertyLifecycleImpactDto =
  components["schemas"]["PropertyLifecycleImpactApiResponse"];

const propertyStatusSchema = z.enum(["active", "archived"]);

export const propertySummarySchema: z.ZodType<PropertySummaryDto> = z.object({
  id: z.uuid(),
  name: z.string(),
  shortName: z.string().nullable(),
  address: z.string().nullable(),
  status: propertyStatusSchema,
  archivedAt: z.iso.datetime({ offset: true }).nullable(),
  updatedAt: z.iso.datetime({ offset: true }),
  capabilities: z.object({
    canUpdate: z.boolean(),
    canArchive: z.boolean(),
    canRestore: z.boolean(),
  }),
});

export const propertyDirectorySchema: z.ZodType<PropertyDirectoryDto> =
  z.object({
    items: z.array(propertySummarySchema),
    capabilities: z.object({
      canCreate: z.boolean(),
      readonlyReasonCode: z.enum(["financial_write_forbidden"]).nullable(),
    }),
  });

export type PropertyDirectoryLoadResult =
  | { status: "success"; directory: PropertyDirectoryDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export type CreatePropertyDraft = {
  name: string;
  shortName: string;
  address: string;
};

export type CreatePropertyResult =
  | { status: "success"; property: PropertySummaryDto }
  | { status: "unauthenticated" }
  | { status: "forbidden"; message: string }
  | ({ status: "error" } & ApiErrorDetails);

export type UpdatePropertyDraft = CreatePropertyDraft & {
  expectedUpdatedAt: string;
};

export type UpdatePropertyResult =
  | { status: "success"; property: PropertySummaryDto }
  | { status: "unauthenticated" }
  | { status: "forbidden"; message: string }
  | { status: "not_found"; message: string }
  | { status: "conflict"; message: string }
  | ({ status: "error" } & ApiErrorDetails);

export type PropertyLifecycleAction = "archive" | "restore";

export type PropertyLifecycleResult =
  | {
      status: "success";
      property: PropertySummaryDto;
      impact: PropertyLifecycleImpactDto;
    }
  | { status: "unauthenticated" }
  | { status: "forbidden"; message: string }
  | { status: "not_found"; message: string }
  | { status: "conflict"; message: string }
  | ({ status: "error" } & ApiErrorDetails);

const propertyLifecycleResponseSchema = z.object({
  property: propertySummarySchema,
  impact: z.object({
    historyPreserved: z.boolean(),
    activeRulesUnchanged: z.boolean(),
    availableForNewReferences: z.boolean(),
  }),
});

export async function loadProperties(
  signal?: AbortSignal,
): Promise<PropertyDirectoryLoadResult> {
  const response = await requestJson("/api/v1/properties", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) {
    return { status: "unauthenticated" };
  }
  if (!response.ok) {
    return {
      status: "error",
      message: `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = propertyDirectorySchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      message: "API вернул список объектов неожиданного формата.",
    };
  }
  return { status: "success", directory: parsed.data };
}

export async function createProperty({
  csrfToken,
  draft,
}: {
  csrfToken: string;
  draft: CreatePropertyDraft;
}): Promise<CreatePropertyResult> {
  const response = await requestJson("/api/v1/properties", {
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
      message: apiError?.message ?? "Создание объекта недоступно.",
    };
  }
  if (!response.ok) {
    return {
      status: "error",
      code: apiError?.code ?? "property_create_failed",
      fieldErrors: apiError?.fieldErrors ?? {},
      message: apiError?.message ?? "Не удалось создать объект.",
    };
  }
  const parsed = propertySummarySchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      code: "invalid_property_response",
      fieldErrors: {},
      message: "API вернул созданный объект неожиданного формата.",
    };
  }
  return { status: "success", property: parsed.data };
}

export async function updateProperty({
  csrfToken,
  draft,
  propertyId,
}: {
  csrfToken: string;
  draft: UpdatePropertyDraft;
  propertyId: string;
}): Promise<UpdatePropertyResult> {
  const response = await requestJson(`/api/v1/properties/${propertyId}`, {
    body: JSON.stringify(draft),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    method: "PUT",
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
      message: apiError?.message ?? "Изменение объекта недоступно.",
    };
  }
  if (response.httpStatus === 404) {
    return {
      status: "not_found",
      message: apiError?.message ?? "Объект не найден.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: apiError?.message ?? "Объект уже изменился. Обновите данные.",
    };
  }
  if (!response.ok) {
    return {
      status: "error",
      code: apiError?.code ?? "property_update_failed",
      fieldErrors: apiError?.fieldErrors ?? {},
      message: apiError?.message ?? "Не удалось изменить объект.",
    };
  }
  const parsed = propertySummarySchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      code: "invalid_property_response",
      fieldErrors: {},
      message: "API вернул изменённый объект неожиданного формата.",
    };
  }
  return { status: "success", property: parsed.data };
}

export async function changePropertyLifecycle({
  action,
  csrfToken,
  property,
}: {
  action: PropertyLifecycleAction;
  csrfToken: string;
  property: Pick<PropertySummaryDto, "id" | "status" | "updatedAt">;
}): Promise<PropertyLifecycleResult> {
  const response = await requestJson(
    `/api/v1/properties/${property.id}/${action}`,
    {
      body: JSON.stringify({
        expectedStatus: property.status,
        expectedUpdatedAt: property.updatedAt,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
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
      message: apiError?.message ?? "Изменение состояния объекта недоступно.",
    };
  }
  if (response.httpStatus === 404) {
    return {
      status: "not_found",
      message: apiError?.message ?? "Объект не найден.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: apiError?.message ?? "Объект уже изменился. Обновите список.",
    };
  }
  if (!response.ok) {
    return {
      status: "error",
      code: apiError?.code ?? "property_lifecycle_failed",
      fieldErrors: apiError?.fieldErrors ?? {},
      message: apiError?.message ?? "Не удалось изменить состояние объекта.",
    };
  }
  const parsed = propertyLifecycleResponseSchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      code: "invalid_property_lifecycle_response",
      fieldErrors: {},
      message: "API вернул состояние объекта неожиданного формата.",
    };
  }
  return {
    status: "success",
    property: parsed.data.property,
    impact: parsed.data.impact,
  };
}
