import { z } from "zod";

import type { components } from "../../../api/generated/schema";

export type ManualLedgerDto =
  components["schemas"]["ManualLedgerListApiResponse"];
export type ManualOperationDto =
  components["schemas"]["ManualOperationApiResponse"];
export type ManualOperationEditDto =
  components["schemas"]["ManualOperationEditApiResponse"];

const operationTypeSchema = z.enum([
  "income",
  "expense",
  "transfer",
  "adjustment",
]);
const operationStatusSchema = z.enum([
  "draft",
  "needs_review",
  "confirmed",
  "ignored",
  "duplicate",
]);
const namedReferenceSchema = z.object({ id: z.uuid(), name: z.string() });
const operationCapabilitiesSchema = z.object({
  canEdit: z.boolean(),
  canCancel: z.boolean(),
  canRestore: z.boolean(),
  canDelete: z.boolean(),
  readonlyReason: z.string().nullable(),
});
const filterOptionsSchema = z.object({
  accounts: z.array(
    namedReferenceSchema.extend({
      currency: z.string(),
    }),
  ),
  categories: z.array(namedReferenceSchema),
  properties: z.array(namedReferenceSchema),
  perPage: z.array(z.number().int()),
});

export const manualOperationSchema: z.ZodType<ManualOperationDto> = z.object({
  id: z.uuid(),
  version: z.number().int(),
  operationType: operationTypeSchema,
  operationDate: z.iso.date(),
  description: z.string(),
  status: operationStatusSchema,
  money: z
    .object({
      amount: z.string(),
      currency: z.string(),
    })
    .nullable(),
  account: namedReferenceSchema.nullable(),
  sourceAccount: namedReferenceSchema.nullable(),
  destinationAccount: namedReferenceSchema.nullable(),
  category: namedReferenceSchema.nullable(),
  property: namedReferenceSchema.nullable(),
  capabilities: operationCapabilitiesSchema,
});

export const manualLedgerSchema: z.ZodType<ManualLedgerDto> = z.object({
  items: z.array(manualOperationSchema),
  pagination: z.object({
    page: z.number().int(),
    perPage: z.number().int(),
    total: z.number().int(),
    totalPages: z.number().int(),
    hasPrevious: z.boolean(),
    hasNext: z.boolean(),
  }),
  filterOptions: filterOptionsSchema,
  capabilities: z.object({
    canCreate: z.boolean(),
    readonlyReason: z.string().nullable(),
  }),
  targetOperationId: z.uuid().nullable(),
});

const manualOperationEditSchema: z.ZodType<ManualOperationEditDto> = z.object({
  operation: manualOperationSchema,
  filterOptions: filterOptionsSchema,
});

export type ManualLedgerLoadResult =
  | { status: "success"; ledger: ManualLedgerDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export async function loadManualLedger(
  search: string,
): Promise<ManualLedgerLoadResult> {
  try {
    const response = await fetch(`/api/v1/manual-ledger${search}`, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (response.status === 401) {
      return { status: "unauthenticated" };
    }
    if (!response.ok) {
      return {
        status: "error",
        message: `API вернул статус ${response.status}.`,
      };
    }

    const parsed = manualLedgerSchema.safeParse(await response.json());
    if (!parsed.success) {
      return {
        status: "error",
        message: "API вернул данные manual ledger неожиданного формата.",
      };
    }
    return { status: "success", ledger: parsed.data };
  } catch {
    return { status: "error", message: "Backend недоступен." };
  }
}

export type ManualOperationEditLoadResult =
  | { status: "success"; edit: ManualOperationEditDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export async function loadManualOperationEdit(
  operationId: string,
): Promise<ManualOperationEditLoadResult> {
  try {
    const response = await fetch(`/api/v1/manual-ledger/${operationId}/edit`, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (response.status === 401) {
      return { status: "unauthenticated" };
    }
    if (!response.ok) {
      return {
        status: "error",
        message: `Не удалось загрузить форму: статус ${response.status}.`,
      };
    }
    const parsed = manualOperationEditSchema.safeParse(await response.json());
    return parsed.success
      ? { status: "success", edit: parsed.data }
      : { status: "error", message: "API вернул форму неожиданного формата." };
  } catch {
    return { status: "error", message: "Backend недоступен." };
  }
}
