import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { requestJson } from "../../../api/transport";

export type OperationsDto = components["schemas"]["OperationsListApiResponse"];
export type OperationDto = components["schemas"]["OperationApiResponse"];

const namedReferenceSchema = z.object({ id: z.uuid(), name: z.string() });
const accountReferenceSchema = namedReferenceSchema.extend({
  currency: z.string(),
});
const capabilitiesSchema = z.object({
  canEdit: z.boolean(),
  editKind: z.enum(["manual", "imported", "none"]),
  canCancel: z.boolean(),
  canRestore: z.boolean(),
  canDelete: z.boolean(),
  readonlyReason: z
    .enum([
      "financial_write_forbidden",
      "operation_state_readonly",
      "source_workflow_required",
      "system_operation",
    ])
    .nullable(),
});
const provenanceSchema = z.discriminatedUnion("kind", [
  z.object({
    kind: z.literal("import"),
    uploadedDocumentId: z.uuid().nullable(),
    rawTransactionId: z.uuid().nullable(),
  }),
  z.object({ kind: z.literal("debt"), debtAccountId: z.uuid().nullable() }),
  z.object({ kind: z.literal("system") }),
]);

export const operationSchema: z.ZodType<OperationDto> = z.object({
  id: z.uuid(),
  version: z.number().int(),
  operationType: z.enum(["income", "expense", "transfer", "adjustment"]),
  source: z.enum(["manual", "bank_pdf", "debt", "system"]),
  status: z.enum([
    "draft",
    "needs_review",
    "confirmed",
    "ignored",
    "duplicate",
  ]),
  operationDate: z.iso.date(),
  description: z.string(),
  money: z.object({ amount: z.string(), currency: z.string() }).nullable(),
  account: accountReferenceSchema.nullable(),
  sourceAccount: accountReferenceSchema.nullable(),
  destinationAccount: accountReferenceSchema.nullable(),
  category: namedReferenceSchema.nullable(),
  property: namedReferenceSchema.nullable(),
  provenance: provenanceSchema.nullable(),
  capabilities: capabilitiesSchema,
});

export const operationsSchema: z.ZodType<OperationsDto> = z.object({
  items: z.array(operationSchema),
  pagination: z.object({
    page: z.number().int(),
    perPage: z.number().int(),
    total: z.number().int(),
    totalPages: z.number().int(),
    hasPrevious: z.boolean(),
    hasNext: z.boolean(),
  }),
  filterOptions: z.object({
    accounts: z.array(
      accountReferenceSchema.extend({
        canRecordIncome: z.boolean(),
        canRecordExpense: z.boolean(),
        canTransfer: z.boolean(),
      }),
    ),
    categories: z.array(namedReferenceSchema),
    properties: z.array(namedReferenceSchema),
    sources: z.array(z.enum(["manual", "bank_pdf", "debt", "system"])),
    perPage: z.array(z.number().int()),
  }),
  capabilities: z.object({
    canCreate: z.boolean(),
    readonlyReason: z.string().nullable(),
  }),
  targetOperationId: z.uuid().nullable(),
  targetOperation: operationSchema.nullable().optional().default(null),
});

export type OperationsLoadResult =
  | { status: "success"; operations: OperationsDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export async function loadOperations(
  search: string,
  signal?: AbortSignal,
): Promise<OperationsLoadResult> {
  const response = await requestJson(`/api/v1/operations${search}`, {
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
  const parsed = operationsSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", operations: parsed.data }
    : { status: "error", message: "API вернул операции неожиданного формата." };
}
