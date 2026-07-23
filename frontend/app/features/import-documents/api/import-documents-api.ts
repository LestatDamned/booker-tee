import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { requestJson } from "../../../api/transport";

export type ImportDocumentListDto =
  components["schemas"]["ImportDocumentListApiResponse"];
export type ImportDocumentListItemDto =
  components["schemas"]["ImportDocumentListItemApiResponse"];

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

export const importDocumentListSchema: z.ZodType<ImportDocumentListDto> =
  z.object({
    workspaceId: z.uuid(),
    workspaceName: z.string(),
    items: z.array(
      z.object({
        id: z.uuid(),
        filename: z.string(),
        status: statusSchema,
        createdAt: z.iso.datetime({ offset: true }),
        fileSizeBytes: z.number().int().nullable(),
        detectedBankName: z.string().nullable(),
        statementPeriod: z
          .object({
            start: z.iso.date(),
            end: z.iso.date(),
          })
          .nullable(),
        account: z
          .object({
            id: z.uuid(),
            name: z.string(),
            currency: z.string(),
            bankName: z.string().nullable(),
          })
          .nullable(),
        totalRowCount: z.number().int(),
        reviewableRowCount: z.number().int(),
        capabilities: z.object({
          canOpenDetail: z.boolean(),
          canMap: z.boolean(),
          canReview: z.boolean(),
        }),
        nextStepKind: z.enum(["detail", "mapping", "review"]),
      }),
    ),
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
        z.object({
          id: z.uuid(),
          name: z.string(),
          currency: z.string(),
          bankName: z.string().nullable(),
        }),
      ),
      perPage: z.array(z.number().int()),
    }),
    summary: z.object({
      totalDocumentCount: z.number().int(),
      attentionDocumentCount: z.number().int(),
    }),
    capabilities: z.object({
      canUpload: z.boolean(),
      readonlyReasonCode: z.enum(["import_management_forbidden"]).nullable(),
    }),
  });

export type ImportDocumentListLoadResult =
  | { status: "success"; documents: ImportDocumentListDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export async function loadImportDocuments(
  search = "",
  signal?: AbortSignal,
): Promise<ImportDocumentListLoadResult> {
  const response = await requestJson(`/api/v1/imports/documents${search}`, {
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
  const parsed = importDocumentListSchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      message: "API вернул список документов неожиданного формата.",
    };
  }
  return { status: "success", documents: parsed.data };
}
