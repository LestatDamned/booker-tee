import { z } from "zod";

import type { components } from "../../../api/generated/schema";

export type ImportReviewDto = components["schemas"]["ImportReviewApiResponse"];

const accountSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  currency: z.string(),
});

const rawTransactionStatusSchema = z.enum([
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
]);

const nullableSourceTextSchema = z.string().nullable();
const validationStatusSchema = z.enum([
  "valid",
  "mismatch",
  "unavailable",
  "needs_review",
]);
const validationReasonSchema = z.enum([
  "totals_match",
  "rows_need_review",
  "balance_chain_mismatch",
  "control_totals_unavailable",
  "control_totals_mismatch",
  "ignored_rows_explain_mismatch",
]);
const nullableDecimalSchema = z.string().nullable();

export const importReviewSchema: z.ZodType<ImportReviewDto> = z.object({
  document: z.object({
    id: z.uuid(),
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
    sourceAccount: accountSchema.nullable(),
  }),
  queue: z.object({
    total: z.number().int().nonnegative(),
    completed: z.number().int().nonnegative(),
    remaining: z.number().int().nonnegative(),
    firstRemainingItemId: z.uuid().nullable(),
    orderedItemIds: z.array(z.uuid()),
  }),
  items: z.array(
    z.object({
      id: z.uuid(),
      rowIndex: z.number().int(),
      status: rawTransactionStatusSchema,
      isTerminal: z.boolean(),
      isReviewable: z.boolean(),
      sourceAccount: accountSchema.nullable(),
      raw: z.object({
        operationDate: nullableSourceTextSchema,
        postingDate: nullableSourceTextSchema,
        description: nullableSourceTextSchema,
        amount: nullableSourceTextSchema,
        currency: nullableSourceTextSchema,
        balanceAfter: nullableSourceTextSchema,
        accountHint: nullableSourceTextSchema,
      }),
      normalized: z.object({
        operationDate: z.iso.date().nullable(),
        postingDate: z.iso.date().nullable(),
        description: nullableSourceTextSchema,
        amount: nullableSourceTextSchema,
        currency: nullableSourceTextSchema,
        balanceAfter: nullableSourceTextSchema,
      }),
    }),
  ),
  validation: z
    .object({
      status: validationStatusSchema,
      reasonCode: validationReasonSchema,
      currency: z.string().nullable(),
      extractedCount: z.number().int().nonnegative(),
      normalizedCount: z.number().int().nonnegative(),
      needsReviewCount: z.number().int().nonnegative(),
      calculatedTotalInflow: z.string(),
      calculatedTotalOutflow: z.string(),
      ignoredTotalInflow: z.string(),
      ignoredTotalOutflow: z.string(),
      statementTotalInflow: nullableDecimalSchema,
      statementTotalOutflow: nullableDecimalSchema,
      openingBalance: nullableDecimalSchema,
      closingBalance: nullableDecimalSchema,
      inflowDifference: nullableDecimalSchema,
      outflowDifference: nullableDecimalSchema,
      unexplainedInflowDifference: nullableDecimalSchema,
      unexplainedOutflowDifference: nullableDecimalSchema,
      balanceChain: z.object({
        status: validationStatusSchema,
        direction: z.string().nullable(),
        checkedPairCount: z.number().int().nonnegative(),
        mismatchCount: z.number().int().nonnegative(),
      }),
      rowProblems: z.array(
        z.object({
          itemId: z.uuid(),
          rowIndex: z.number().int(),
          previousItemId: z.uuid(),
          previousRowIndex: z.number().int(),
          code: z.literal("balance_chain_mismatch"),
          expectedBalanceAfter: z.string(),
          actualBalanceAfter: z.string(),
        }),
      ),
    })
    .nullable(),
  capabilities: z.object({
    canWrite: z.boolean(),
    readonlyReasonCode: z.enum(["financial_write_forbidden"]).nullable(),
  }),
});

export type ImportReviewLoadResult =
  | { status: "success"; review: ImportReviewDto }
  | { status: "unauthenticated" }
  | { status: "forbidden" }
  | { status: "not-found" }
  | { status: "error"; message: string };

export async function loadImportReview(
  documentId: string,
): Promise<ImportReviewLoadResult> {
  try {
    const response = await fetch(`/api/v1/import-review/${documentId}`, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (response.status === 401) {
      return { status: "unauthenticated" };
    }
    if (response.status === 403) {
      return { status: "forbidden" };
    }
    if (response.status === 404) {
      return { status: "not-found" };
    }
    if (!response.ok) {
      return {
        status: "error",
        message: `API вернул статус ${response.status}.`,
      };
    }

    const payload: unknown = await response.json();
    const parsed = importReviewSchema.safeParse(payload);
    if (!parsed.success) {
      return {
        status: "error",
        message: "API вернул данные import review неожиданного формата.",
      };
    }
    return { status: "success", review: parsed.data };
  } catch {
    return { status: "error", message: "Backend недоступен." };
  }
}
