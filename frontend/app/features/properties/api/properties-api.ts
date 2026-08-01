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
