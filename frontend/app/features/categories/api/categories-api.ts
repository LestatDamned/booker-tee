import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { requestJson } from "../../../api/transport";

export type CategoryDirectoryDto =
  components["schemas"]["CategoryDirectoryApiResponse"];
export type CategorySummaryDto =
  components["schemas"]["CategorySummaryApiResponse"];
export type CategoryKind = components["schemas"]["CategoryKind"];

const categoryKindSchema = z.enum([
  "income",
  "expense",
  "transfer",
  "adjustment",
  "mixed",
]);

const categorySummarySchema: z.ZodType<CategorySummaryDto> = z.object({
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
  updatedAt: z.iso.datetime({ offset: true }),
  capabilities: z.object({
    canUpdate: z.boolean(),
    canArchive: z.boolean(),
    canRestore: z.boolean(),
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
