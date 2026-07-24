import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

export type ImportUploadReferenceDto =
  components["schemas"]["ImportUploadReferenceApiResponse"];
export type ImportDocumentUploadDto =
  components["schemas"]["ImportDocumentUploadApiResponse"];

const uploadReferenceSchema: z.ZodType<ImportUploadReferenceDto> = z.object({
  accounts: z.array(
    z.object({
      id: z.uuid(),
      name: z.string(),
      currency: z.string(),
      bankName: z.string().nullable(),
    }),
  ),
  acceptedExtensions: z.array(z.string()),
  acceptedContentTypes: z.array(z.string()),
  maxFileSizeBytes: z.number().int().positive(),
  canUpload: z.boolean(),
});

const uploadResponseSchema: z.ZodType<ImportDocumentUploadDto> = z.object({
  id: z.uuid(),
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
  replayed: z.boolean(),
  navigationTarget: z.literal("document_detail"),
  nextStep: z.enum(["mapping", "review", "upload", "document_list"]),
});

export type ImportUploadReferenceLoadResult =
  | { status: "success"; reference: ImportUploadReferenceDto }
  | { status: "unauthenticated" }
  | { status: "forbidden" }
  | { status: "error"; message: string };

export type ImportUploadResult =
  | { status: "success"; document: ImportDocumentUploadDto }
  | { status: "unauthenticated" }
  | {
      status: "conflict" | "error";
      code?: string | undefined;
      fieldErrors: Record<string, string[]>;
      message: string;
    };

export async function loadImportUploadReference(
  signal?: AbortSignal,
): Promise<ImportUploadReferenceLoadResult> {
  const response = await requestJson("/api/v1/imports/upload-reference", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (response.httpStatus === 403) return { status: "forbidden" };
  if (!response.ok) {
    return {
      status: "error",
      message: `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = uploadReferenceSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", reference: parsed.data }
    : {
        status: "error",
        message: "API вернул настройки загрузки неожиданного формата.",
      };
}

export async function uploadImportDocument({
  accountId,
  csrfToken,
  file,
  idempotencyKey,
}: {
  accountId: string;
  csrfToken: string;
  file: File;
  idempotencyKey: string;
}): Promise<ImportUploadResult> {
  const body = new FormData();
  body.set("account_id", accountId);
  body.set("statement", file);
  const response = await requestJson("/api/v1/imports/documents", {
    method: "POST",
    headers: {
      "Idempotency-Key": idempotencyKey,
      "X-CSRF-Token": csrfToken,
    },
    body,
  });
  if (response.status === "network_error") {
    return {
      status: "error",
      fieldErrors: {},
      message:
        "Связь прервалась. Повторите отправку: уже сохранённый документ не продублируется.",
    };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    const error = parseApiError(response.body);
    return {
      status: response.httpStatus === 409 ? "conflict" : "error",
      code: error?.code,
      fieldErrors: error?.fieldErrors ?? {},
      message: error?.message ?? `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = uploadResponseSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", document: parsed.data }
    : {
        status: "error",
        fieldErrors: {},
        message: "API вернул результат загрузки неожиданного формата.",
      };
}
