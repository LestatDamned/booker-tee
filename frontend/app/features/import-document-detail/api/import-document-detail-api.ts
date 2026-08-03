import { z } from "zod";

import {
  apiLoadError,
  apiLoadNetworkError,
  apiResponseErrorMessage,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
  type ApiLoadError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

export type ImportDocumentDetailDto =
  components["schemas"]["ImportDocumentDetailApiResponse"];
export type ImportDocumentManagementAction = "ignore" | "delete";

const statusSchema = z.enum([
  "uploaded",
  "pending_parse",
  "parsing",
  "parsed",
  "requires_review",
  "failed_to_parse",
  "imported",
  "ignored",
]);
const workflowStateSchema = z.enum([
  "pending",
  "current",
  "done",
  "skipped",
  "blocked",
]);
const capabilitySchema = z.object({
  allowed: z.boolean(),
  blockingReasonCodes: z.array(
    z.enum([
      "import_management_forbidden",
      "linked_operations_exist",
      "already_ignored",
    ]),
  ),
});

export const importDocumentDetailSchema: z.ZodType<ImportDocumentDetailDto> =
  z.object({
    id: z.uuid(),
    filename: z.string(),
    status: statusSchema,
    bankName: z.string().nullable(),
    statementType: z.string().nullable(),
    statementPeriodStart: z.iso.date().nullable(),
    statementPeriodEnd: z.iso.date().nullable(),
    fileSizeBytes: z.number().int().nullable(),
    createdAt: z.iso.datetime({ offset: true }).nullable(),
    updatedAt: z.iso.datetime({ offset: true }).nullable(),
    account: z
      .object({
        id: z.uuid(),
        name: z.string(),
        currency: z.string(),
      })
      .nullable(),
    workflow: z.object({
      upload: workflowStateSchema,
      extract: workflowStateSchema,
      mapping: workflowStateSchema,
      review: workflowStateSchema,
      ledger: workflowStateSchema,
    }),
    nextStep: z.enum(["mapping", "review", "upload", "document_list"]),
    validation: z
      .object({
        status: z.string(),
        reasonCode: z.enum([
          "totals_match",
          "rows_need_review",
          "balance_chain_mismatch",
          "control_totals_unavailable",
          "control_totals_mismatch",
          "ignored_rows_explain_mismatch",
          "needs_mapping",
          "validation_failed",
        ]),
        message: z.string(),
        extractedCount: z.number().int().nullable(),
        calculatedTotalInflow: z.string().nullable(),
        calculatedTotalOutflow: z.string().nullable(),
        ignoredRowCount: z.number().int(),
        ignoredTotalInflow: z.string().nullable(),
        ignoredTotalOutflow: z.string().nullable(),
        currency: z.string().nullable(),
        tableCount: z.number().int().nullable(),
        needsMapping: z.boolean(),
      })
      .nullable(),
    rawRows: z.object({
      items: z.array(
        z.object({
          rowIndex: z.number().int(),
          status: z.enum([
            "extracted",
            "normalized",
            "suggested",
            "needs_review",
            "matched",
            "ignored",
            "duplicate",
            "possible_duplicate",
            "failed",
            "confirmed",
          ]),
          displayDate: z.string().nullable(),
          amount: z.string().nullable(),
          amountRaw: z.string().nullable(),
          currency: z.string().nullable(),
          description: z.string(),
          normalizationError: z.string(),
        }),
      ),
      total: z.number().int(),
      limit: z.number().int(),
    }),
    parseAttempts: z.object({
      items: z.array(
        z.object({
          id: z.uuid(),
          status: z.enum(["running", "success", "requires_review", "failed"]),
          parserName: z.string(),
          parserVersion: z.string().nullable(),
          startedAt: z.iso.datetime({ offset: true }),
          finishedAt: z.iso.datetime({ offset: true }).nullable(),
          message: z.string(),
        }),
      ),
      total: z.number().int(),
      limit: z.number().int(),
    }),
    capabilities: z.object({
      canManage: z.boolean(),
      ignore: capabilitySchema,
      delete: capabilitySchema,
    }),
  });

export type ImportDocumentDetailLoadResult =
  | { status: "success"; document: ImportDocumentDetailDto }
  | ApiUnauthenticatedFailure
  | { status: "forbidden" }
  | { status: "not_found" }
  | ApiLoadError;

export type ImportDocumentMutationResult =
  | { status: "success"; document?: ImportDocumentDetailDto }
  | ApiUnauthenticatedFailure
  | { status: "conflict" | "error"; message: string };

export async function loadImportDocumentDetail(
  documentId: string,
  signal?: AbortSignal,
): Promise<ImportDocumentDetailLoadResult> {
  const response = await requestJson(
    `/api/v1/imports/documents/${documentId}`,
    {
      ...(signal ? { signal } : {}),
    },
  );
  if (response.status === "network_error") {
    return apiLoadNetworkError();
  }
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 403) return { status: "forbidden" };
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) {
    return apiUnexpectedStatusError(response.httpStatus);
  }
  const parsed = importDocumentDetailSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", document: parsed.data }
    : apiLoadError("API вернул документ неожиданного формата.");
}

export async function mutateImportDocument(
  document: ImportDocumentDetailDto,
  action: ImportDocumentManagementAction,
  csrfToken: string,
): Promise<ImportDocumentMutationResult> {
  const response = await requestJson(
    `/api/v1/imports/documents/${document.id}${action === "delete" ? "" : `/${action}`}`,
    {
      method: action === "delete" ? "DELETE" : "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ expectedStatus: document.status }),
    },
  );
  if (response.status === "network_error") {
    return apiLoadNetworkError();
  }
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message:
        parseApiError(response.body)?.message ??
        "Состояние документа изменилось.",
    };
  }
  if (!response.ok) {
    return apiLoadError(
      apiResponseErrorMessage(
        parseApiError(response.body),
        response.httpStatus,
      ),
    );
  }
  if (action === "delete") return { status: "success" };
  const parsed = importDocumentDetailSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", document: parsed.data }
    : apiLoadError("API вернул документ неожиданного формата.");
}
