import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

export type ImportMappingDto = components["schemas"]["MappingReadApiResponse"];
export type ImportMappingCommand =
  components["schemas"]["MappingCommandApiModel"];
export type ImportMappingPreviewDto =
  components["schemas"]["MappingPreviewApiResponse"];
export type ImportMappingCommitDto =
  components["schemas"]["MappingImportApiResponse"];
export type ImportMappingSourceTable =
  components["schemas"]["MappingSourceTableApiResponse"];
export type ImportMappingControlTotalCell =
  components["schemas"]["MappingControlTotalCellApiModel"];
export type ImportMappingSourceRows =
  components["schemas"]["MappingSourceRowsApiResponse"];

const tableRefSchema = z.object({
  pageNumber: z.number().int().min(1),
  tableIndex: z.number().int().min(0),
});

const controlTotalCellSchema = z.object({
  tableRef: tableRefSchema,
  rowNumber: z.number().int().min(1),
  columnIndex: z.number().int().min(0),
});

export const mappingCommandSchema: z.ZodType<ImportMappingCommand> = z.object({
  tableRef: tableRefSchema,
  operationDateColumn: z.number().int().min(0),
  postingDateColumn: z.number().int().min(0).nullable(),
  descriptionColumn: z.number().int().min(0),
  amountColumn: z.number().int().min(0).nullable(),
  debitAmountColumn: z.number().int().min(0).nullable(),
  creditAmountColumn: z.number().int().min(0).nullable(),
  currencyColumn: z.number().int().min(0).nullable(),
  balanceAfterColumn: z.number().int().min(0).nullable(),
  firstDataRowNumber: z.number().int().min(1),
  defaultCurrency: z.string().length(3),
  unsignedAmountDirection: z.enum(["require_sign", "income", "expense"]),
  openingBalanceCell: controlTotalCellSchema.nullable(),
  closingBalanceCell: controlTotalCellSchema.nullable(),
});

const candidateSchema = z.object({
  field: z.string(),
  columnIndex: z.number().int().min(0),
  header: z.string(),
});

const suggestionReasonSchema = z.object({
  field: z.string(),
  columnIndex: z.number().int().min(0),
  header: z.string(),
  evidence: z.string(),
  matchedCount: z.number().int().nullable(),
  sampleCount: z.number().int().nullable(),
});

const sourceTableSchema = z.object({
  ref: tableRefSchema,
  sourceType: z.string(),
  rowCount: z.number().int().min(0),
  columnCount: z.number().int().min(0),
  isContinuation: z.boolean(),
  sampleRows: z.array(
    z.object({
      rowNumber: z.number().int().min(1),
      cells: z.array(z.string()),
    }),
  ),
  candidates: z.array(candidateSchema),
  suggestion: z
    .object({
      mapping: mappingCommandSchema,
      reasons: z.array(suggestionReasonSchema),
      warningCodes: z.array(z.string()),
    })
    .nullable(),
});

export const importMappingSchema: z.ZodType<ImportMappingDto> = z.object({
  documentId: z.uuid(),
  filename: z.string(),
  status: z.enum([
    "uploaded",
    "pending_parse",
    "parsing",
    "parsed",
    "requires_review",
    "failed_to_parse",
    "imported",
    "ignored",
  ]),
  bankName: z.string().nullable(),
  statementType: z.string().nullable(),
  account: z
    .object({
      id: z.uuid(),
      name: z.string(),
      currency: z.string(),
    })
    .nullable(),
  defaultCurrency: z.string(),
  capability: z.object({
    allowed: z.boolean(),
    blockingReasonCodes: z.array(
      z.enum([
        "account_required",
        "raw_tables_unavailable",
        "mapping_not_required",
        "confirmed_rows_exist",
      ]),
    ),
  }),
  defaultMapping: mappingCommandSchema,
  defaultSource: z.enum(["template", "analyzer", "fallback"]),
  selectedTemplateId: z.uuid().nullable(),
  templates: z.array(z.object({ id: z.uuid(), name: z.string() })),
  tables: z.array(sourceTableSchema),
  controlTotalCandidates: z.array(
    z.object({
      kind: z.enum(["opening_balance", "closing_balance"]),
      cell: controlTotalCellSchema,
      label: z.string(),
      rawValue: z.string(),
      amount: z.string(),
      currency: z.string(),
      confidence: z.number(),
    }),
  ),
  totalTableCount: z.number().int().min(0),
  tablesTruncated: z.boolean(),
});

const rowErrorCodeSchema = z.enum([
  "operation_date_required",
  "operation_date_invalid",
  "posting_date_invalid",
  "amount_required",
  "amount_invalid",
  "unsigned_amount_direction_required",
  "debit_invalid",
  "credit_invalid",
  "debit_and_credit_present",
  "balance_after_invalid",
  "description_required",
]);

export const importMappingPreviewSchema: z.ZodType<ImportMappingPreviewDto> =
  z.object({
    rows: z.array(
      z.object({
        tableRef: tableRefSchema,
        sourceRowNumber: z.number().int().min(1),
        operationDate: z.iso.date().nullable(),
        operationDateRaw: z.string(),
        postingDate: z.iso.date().nullable(),
        postingDateRaw: z.string(),
        description: z.string(),
        amount: z.string().nullable(),
        amountRaw: z.string(),
        currency: z.string(),
        balanceAfter: z.string().nullable(),
        balanceAfterRaw: z.string(),
        status: z.enum(["valid", "error"]),
        errorCodes: z.array(rowErrorCodeSchema),
      }),
    ),
    totalRowCount: z.number().int().min(0),
    validRowCount: z.number().int().min(0),
    invalidRowCount: z.number().int().min(0),
    rowLimit: z.number().int().min(1),
    rowsTruncated: z.boolean(),
    compatibleTables: z.array(tableRefSchema),
    warnings: z.array(
      z.object({
        code: z.string(),
        severity: z.enum(["warning", "error"]),
        fields: z.array(z.string()),
        affectedRowCount: z.number().int().min(1).nullable(),
      }),
    ),
    controlTotals: z.array(
      z.object({
        kind: z.enum(["opening_balance", "closing_balance"]),
        cell: controlTotalCellSchema,
        rawValue: z.string(),
        amount: z.string(),
        currency: z.string(),
      }),
    ),
    reconciliation: z
      .object({
        openingBalance: z.string(),
        movement: z.string(),
        calculatedClosingBalance: z.string(),
        statementClosingBalance: z.string(),
        difference: z.string(),
        matches: z.boolean(),
      })
      .nullable(),
    canImport: z.boolean(),
  });

const sourceRowsSchema: z.ZodType<ImportMappingSourceRows> = z.object({
  tableRef: tableRefSchema,
  rows: z.array(
    z.object({
      rowNumber: z.number().int().min(1),
      cells: z.array(z.string()),
    }),
  ),
  totalRowCount: z.number().int().min(0),
  startRowNumber: z.number().int().min(1),
  rowLimit: z.number().int().min(1),
  hasPrevious: z.boolean(),
  hasNext: z.boolean(),
});

export const importMappingCommitSchema: z.ZodType<ImportMappingCommitDto> =
  z.object({
    documentId: z.uuid(),
    status: z.enum([
      "uploaded",
      "pending_parse",
      "parsing",
      "parsed",
      "requires_review",
      "failed_to_parse",
      "imported",
      "ignored",
    ]),
    importedRowCount: z.number().int().min(1),
    templateId: z.uuid().nullable(),
    replayed: z.boolean(),
    reviewTarget: z.object({
      kind: z.literal("import_review"),
      documentId: z.uuid(),
    }),
  });

export type ImportMappingLoadResult =
  | { status: "success"; mapping: ImportMappingDto }
  | { status: "unauthenticated" }
  | { status: "forbidden" }
  | { status: "not_found" }
  | { status: "error"; message: string };

export type ImportMappingSourceRowsResult =
  | { status: "success"; source: ImportMappingSourceRows }
  | { status: "unauthenticated" | "not_found" }
  | { status: "error"; message: string };

export type ImportMappingPreviewResult =
  | { status: "success"; preview: ImportMappingPreviewDto }
  | { status: "unauthenticated" }
  | {
      status: "validation_error";
      message: string;
      fieldErrors: Record<string, string[]>;
    }
  | { status: "conflict" | "error"; message: string };

export type ImportMappingCommitResult =
  | { status: "success"; result: ImportMappingCommitDto }
  | { status: "unauthenticated" }
  | {
      status: "validation_error";
      message: string;
      fieldErrors: Record<string, string[]>;
    }
  | { status: "conflict" | "error"; message: string };

export async function loadImportMapping(
  documentId: string,
  signal?: AbortSignal,
): Promise<ImportMappingLoadResult> {
  const response = await requestJson(
    `/api/v1/imports/documents/${documentId}/mapping`,
    signal ? { signal } : {},
  );
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (response.httpStatus === 403) return { status: "forbidden" };
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) {
    return {
      status: "error",
      message:
        parseApiError(response.body)?.message ??
        `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = importMappingSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", mapping: parsed.data }
    : {
        status: "error",
        message: "API вернул настройку колонок неожиданного формата.",
      };
}

export async function loadImportMappingSourceRows({
  documentId,
  rowLimit = 30,
  startRowNumber,
  tableRef,
}: {
  documentId: string;
  rowLimit?: number;
  startRowNumber: number;
  tableRef: ImportMappingCommand["tableRef"];
}): Promise<ImportMappingSourceRowsResult> {
  const query = new URLSearchParams({
    startRowNumber: String(startRowNumber),
    rowLimit: String(rowLimit),
  });
  const response = await requestJson(
    `/api/v1/imports/documents/${documentId}/mapping/tables/${tableRef.pageNumber}/${tableRef.tableIndex}/rows?${query}`,
  );
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) {
    return {
      status: "error",
      message:
        parseApiError(response.body)?.message ??
        `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = sourceRowsSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", source: parsed.data }
    : {
        status: "error",
        message: "API вернул строки таблицы неожиданного формата.",
      };
}

export async function previewImportMapping({
  command,
  csrfToken,
  documentId,
}: {
  command: ImportMappingCommand;
  csrfToken: string;
  documentId: string;
}): Promise<ImportMappingPreviewResult> {
  const response = await requestJson(
    `/api/v1/imports/documents/${documentId}/mapping/preview`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ mapping: command }),
    },
  );
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  const apiError = parseApiError(response.body);
  if (response.httpStatus === 422) {
    return {
      status: "validation_error",
      message: apiError?.message ?? "Проверьте выбранные колонки.",
      fieldErrors: apiError?.fieldErrors ?? {},
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message:
        apiError?.message ??
        "Состояние документа изменилось. Обновите страницу.",
    };
  }
  if (!response.ok) {
    return {
      status: "error",
      message: apiError?.message ?? `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = importMappingPreviewSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", preview: parsed.data }
    : {
        status: "error",
        message: "API вернул предпросмотр неожиданного формата.",
      };
}

export async function commitImportMapping({
  command,
  csrfToken,
  documentId,
  idempotencyKey,
  templateName,
}: {
  command: ImportMappingCommand;
  csrfToken: string;
  documentId: string;
  idempotencyKey: string;
  templateName: string | null;
}): Promise<ImportMappingCommitResult> {
  const response = await requestJson(
    `/api/v1/imports/documents/${documentId}/mapping/import`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({
        mapping: command,
        templateName,
      }),
    },
  );
  if (response.status === "network_error") {
    return {
      status: "error",
      message:
        "Связь с backend прервалась. Повторите импорт — строки не продублируются.",
    };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  const apiError = parseApiError(response.body);
  if (response.httpStatus === 422) {
    return {
      status: "validation_error",
      message: apiError?.message ?? "Проверьте настройку импорта.",
      fieldErrors: apiError?.fieldErrors ?? {},
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message:
        apiError?.message ??
        "Состояние документа изменилось. Обновите страницу.",
    };
  }
  if (!response.ok) {
    return {
      status: "error",
      message: apiError?.message ?? `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = importMappingCommitSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", result: parsed.data }
    : {
        status: "error",
        message: "API вернул результат импорта неожиданного формата.",
      };
}
