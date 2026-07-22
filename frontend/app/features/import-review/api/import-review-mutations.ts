import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import {
  importReviewCategoryReferenceSchema,
  importReviewSchema,
} from "./import-review-api";

export type ImportReviewDraftEvaluationRequest =
  components["schemas"]["ImportReviewDraftEvaluationApiRequest"];
export type ImportReviewDraftEvaluationDto =
  components["schemas"]["ImportReviewDraftEvaluationApiResponse"];
export type ImportReviewCategoryCreateRequest =
  components["schemas"]["ImportReviewCategoryCreateApiRequest"];
export type ImportReviewCategoryReferenceDto =
  components["schemas"]["ImportReviewCategoryReferenceApiResponse"];
export type ImportReviewTransferRequest =
  | components["schemas"]["ImportReviewNewTransferApiRequest"]
  | components["schemas"]["ImportReviewRawRowMatchApiRequest"]
  | components["schemas"]["ImportReviewExistingTransferLinkApiRequest"];
export type ImportReviewTransferMutationDto =
  components["schemas"]["ImportReviewTransferMutationApiResponse"];
export type ImportReviewLifecycleRequest =
  components["schemas"]["ImportReviewLifecycleApiRequest"];
export type ImportReviewLifecycleMutationDto =
  components["schemas"]["ImportReviewLifecycleMutationApiResponse"];
export type ImportReviewConfirmationRequest =
  components["schemas"]["ImportReviewConfirmationApiRequest"];
export type ImportReviewUndoRequest =
  components["schemas"]["ImportReviewUndoApiRequest"];
export type ImportReviewPostingMutationDto =
  components["schemas"]["ImportReviewPostingMutationApiResponse"];
export type ImportReviewRuleApplicationDto =
  components["schemas"]["ImportReviewRuleApplicationApiResponse"];

const operationTypeSchema = z.enum([
  "income",
  "expense",
  "transfer",
  "adjustment",
]);
const draftEvaluationSchema: z.ZodType<ImportReviewDraftEvaluationDto> =
  z.object({
    itemId: z.uuid(),
    classification: z.object({
      operationType: operationTypeSchema.nullable(),
      source: z.enum(["explicit", "suggested", "inferred", "unknown"]),
    }),
    selection: z.object({
      categoryId: z.uuid().nullable(),
      propertyId: z.uuid().nullable(),
    }),
    confirmability: z.object({
      canConfirm: z.boolean(),
      blockingReasonCodes: z.array(
        z.enum([
          "terminal_state",
          "failed_state",
          "duplicate_review_required",
          "normalization_error",
          "missing_operation_date",
          "missing_amount",
          "missing_currency",
          "missing_source_account",
          "missing_operation_type",
          "operation_type_amount_mismatch",
          "missing_category",
          "uncategorized_category",
          "transfer_accounts_required",
          "same_transfer_account",
          "unsupported_operation_type",
        ]),
      ),
    }),
    ruleSuggestion: z.object({
      isActive: z.boolean(),
      wasAutoApplied: z.boolean(),
      ruleId: z.uuid().nullable(),
      ruleName: z.string().nullable(),
      pattern: z.string().nullable(),
      operationType: operationTypeSchema.nullable(),
      categoryId: z.uuid().nullable(),
      propertyId: z.uuid().nullable(),
    }),
  });

const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    fieldErrors: z.record(z.string(), z.array(z.string())).nullish(),
  }),
});
const transferMutationSchema: z.ZodType<ImportReviewTransferMutationDto> =
  z.object({
    primaryDocumentId: z.uuid(),
    updatedItemIds: z.array(z.uuid()),
    validationDocumentIds: z.array(z.uuid()),
    reviews: z.array(importReviewSchema),
  });
const lifecycleMutationSchema: z.ZodType<ImportReviewLifecycleMutationDto> =
  z.object({
    itemId: z.uuid(),
    documentId: z.uuid(),
    replayed: z.boolean(),
    review: importReviewSchema,
  });
const postingMutationSchema: z.ZodType<ImportReviewPostingMutationDto> =
  z.object({
    primaryDocumentId: z.uuid(),
    itemId: z.uuid(),
    operationId: z.uuid(),
    updatedItemIds: z.array(z.uuid()),
    replayed: z.boolean(),
    reviews: z.array(importReviewSchema),
  });
const ruleApplicationSchema: z.ZodType<ImportReviewRuleApplicationDto> =
  z.object({
    documentId: z.uuid(),
    checkedCount: z.number().int().nonnegative(),
    suggestedCount: z.number().int().nonnegative(),
    updatedItemIds: z.array(z.uuid()),
    review: importReviewSchema,
  });

export type ImportReviewMutationResult<T> =
  | { status: "success"; data: T }
  | { status: "unauthenticated" | "forbidden" }
  | {
      status: "validation_error";
      message: string;
      fieldErrors: Record<string, string[]>;
    }
  | { status: "conflict"; message: string }
  | { status: "error"; message: string };

export async function evaluateImportReviewDraft(
  documentId: string,
  itemId: string,
  request: ImportReviewDraftEvaluationRequest,
  csrfToken: string,
): Promise<ImportReviewMutationResult<ImportReviewDraftEvaluationDto>> {
  return sendMutation(
    `/api/v1/import-review/${documentId}/items/${itemId}/draft-evaluation`,
    request,
    csrfToken,
    draftEvaluationSchema,
  );
}

export async function createImportReviewCategory(
  documentId: string,
  itemId: string,
  request: ImportReviewCategoryCreateRequest,
  csrfToken: string,
): Promise<ImportReviewMutationResult<ImportReviewCategoryReferenceDto>> {
  return sendMutation(
    `/api/v1/import-review/${documentId}/items/${itemId}/categories`,
    request,
    csrfToken,
    importReviewCategoryReferenceSchema,
  );
}

export async function postImportReviewTransfer(
  documentId: string,
  itemId: string,
  request: ImportReviewTransferRequest,
  csrfToken: string,
  idempotencyKey: string,
): Promise<ImportReviewMutationResult<ImportReviewTransferMutationDto>> {
  return sendMutation(
    `/api/v1/import-review/${documentId}/items/${itemId}/transfer`,
    request,
    csrfToken,
    transferMutationSchema,
    idempotencyKey,
  );
}

export async function updateImportReviewLifecycle(
  documentId: string,
  itemId: string,
  request: ImportReviewLifecycleRequest,
  csrfToken: string,
): Promise<ImportReviewMutationResult<ImportReviewLifecycleMutationDto>> {
  return sendMutation(
    `/api/v1/import-review/${documentId}/items/${itemId}/lifecycle`,
    request,
    csrfToken,
    lifecycleMutationSchema,
  );
}

export async function confirmImportReviewItem(
  documentId: string,
  itemId: string,
  request: ImportReviewConfirmationRequest,
  csrfToken: string,
  idempotencyKey: string,
): Promise<ImportReviewMutationResult<ImportReviewPostingMutationDto>> {
  return sendMutation(
    `/api/v1/import-review/${documentId}/items/${itemId}/confirm`,
    request,
    csrfToken,
    postingMutationSchema,
    idempotencyKey,
  );
}

export async function undoImportReviewPosting(
  documentId: string,
  itemId: string,
  request: ImportReviewUndoRequest,
  csrfToken: string,
): Promise<ImportReviewMutationResult<ImportReviewPostingMutationDto>> {
  return sendMutation(
    `/api/v1/import-review/${documentId}/items/${itemId}/undo-posting`,
    request,
    csrfToken,
    postingMutationSchema,
  );
}

export async function applyRulesToImportReview(
  documentId: string,
  csrfToken: string,
): Promise<ImportReviewMutationResult<ImportReviewRuleApplicationDto>> {
  return sendMutation(
    `/api/v1/import-review/${documentId}/apply-rules`,
    {},
    csrfToken,
    ruleApplicationSchema,
  );
}

async function sendMutation<T>(
  url: string,
  request: object,
  csrfToken: string,
  schema: z.ZodType<T>,
  idempotencyKey?: string,
): Promise<ImportReviewMutationResult<T>> {
  try {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
        ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
      },
      body: JSON.stringify(request),
    });
    if (response.status === 401) return { status: "unauthenticated" };
    if (response.status === 403) return { status: "forbidden" };

    const body: unknown = await response.json();
    if (response.ok) {
      const parsed = schema.safeParse(body);
      return parsed.success
        ? { status: "success", data: parsed.data }
        : {
            status: "error",
            message: "API вернул данные неожиданного формата.",
          };
    }
    const error = apiErrorSchema.safeParse(body);
    if (!error.success) {
      return {
        status: "error",
        message: `API вернул статус ${response.status}.`,
      };
    }
    if (response.status === 422) {
      return {
        status: "validation_error",
        message: error.data.error.message,
        fieldErrors: error.data.error.fieldErrors ?? {},
      };
    }
    if (response.status === 409) {
      return { status: "conflict", message: error.data.error.message };
    }
    return { status: "error", message: error.data.error.message };
  } catch {
    return { status: "error", message: "Backend недоступен." };
  }
}
