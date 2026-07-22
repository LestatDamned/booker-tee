import type { ImportReviewDto } from "./api/import-review-api";

export const reviewDocumentId = "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8";
export const completedItemId = "74d26880-543e-459f-a2a2-9f1a497914fe";
export const remainingItemId = "cb1b2959-b134-4a57-b2f4-7a7dfe8e8a42";
export const expenseCategoryId = "078d4cda-d476-4bd6-b731-92d423d07c39";
export const uncategorizedCategoryId = "5c1fed65-56a7-4210-b8db-e63401b411af";
export const propertyId = "47d25198-3c11-4610-b02d-1df9aff0dc48";
export const confirmedOperationId = "d8e31a25-7ebf-46f9-a587-b2d5a63bd7c3";

export function importReviewPayload(): ImportReviewDto {
  return {
    document: {
      id: reviewDocumentId,
      filename: "statement.pdf",
      status: "requires_review",
      sourceAccount: {
        id: "4958dd80-af47-4131-8f16-16c0ca04f63c",
        name: "Основной счёт",
        currency: "RUB",
      },
    },
    queue: {
      total: 2,
      completed: 1,
      remaining: 1,
      firstRemainingItemId: remainingItemId,
      orderedItemIds: [completedItemId, remainingItemId],
    },
    items: [
      importReviewItem({
        id: completedItemId,
        rowIndex: 1,
        status: "confirmed",
        isTerminal: true,
        isReviewable: false,
      }),
      importReviewItem({
        id: remainingItemId,
        rowIndex: 2,
        status: "matched",
        isTerminal: false,
        isReviewable: true,
      }),
    ],
    references: {
      categories: [
        {
          id: expenseCategoryId,
          name: "Продукты",
          kind: "expense",
          isUncategorized: false,
        },
        {
          id: uncategorizedCategoryId,
          name: "Без категории",
          kind: "mixed",
          isUncategorized: true,
        },
      ],
      properties: [{ id: propertyId, name: "Квартира" }],
    },
    validation: {
      status: "mismatch",
      reasonCode: "balance_chain_mismatch",
      currency: "RUB",
      extractedCount: 2,
      normalizedCount: 2,
      needsReviewCount: 0,
      calculatedTotalInflow: "50000.00",
      calculatedTotalOutflow: "1250.50",
      ignoredTotalInflow: "0.00",
      ignoredTotalOutflow: "0.00",
      statementTotalInflow: "50000.00",
      statementTotalOutflow: "1250.50",
      openingBalance: "11250.50",
      closingBalance: "10000.00",
      inflowDifference: null,
      outflowDifference: null,
      unexplainedInflowDifference: null,
      unexplainedOutflowDifference: null,
      balanceChain: {
        status: "mismatch",
        direction: "ascending",
        checkedPairCount: 1,
        mismatchCount: 1,
      },
      rowProblems: [
        {
          itemId: remainingItemId,
          rowIndex: 2,
          previousItemId: completedItemId,
          previousRowIndex: 1,
          code: "balance_chain_mismatch",
          expectedBalanceAfter: "10000.00",
          actualBalanceAfter: "10050.50",
        },
      ],
    },
    capabilities: { canWrite: true, readonlyReasonCode: null },
  };
}

function importReviewItem(
  overrides: Pick<
    ImportReviewDto["items"][number],
    "id" | "rowIndex" | "status" | "isTerminal" | "isReviewable"
  >,
): ImportReviewDto["items"][number] {
  return {
    ...overrides,
    sourceAccount: {
      id: "4958dd80-af47-4131-8f16-16c0ca04f63c",
      name: "Основной счёт",
      currency: "RUB",
    },
    raw: {
      operationDate: "20.07.2026",
      postingDate: null,
      description: "Покупка в магазине",
      amount: "-1250,50",
      currency: "RUB",
      balanceAfter: "10000,00",
      accountHint: "*1234",
    },
    normalized: {
      operationDate: "2026-07-20",
      postingDate: null,
      description: "Покупка в магазине",
      amount: "-1250.50",
      currency: "RUB",
      balanceAfter: "10000.00",
    },
    classification: { operationType: "expense", source: "inferred" },
    selection: { categoryId: null, propertyId: null },
    confirmability: {
      canConfirm: false,
      blockingReasonCodes: ["missing_category"],
    },
    ruleSuggestion: {
      isActive: false,
      wasAutoApplied: false,
      ruleId: null,
      ruleName: null,
      pattern: null,
      operationType: null,
      categoryId: null,
      propertyId: null,
    },
    posting: {
      operationId:
        overrides.status === "confirmed" ? confirmedOperationId : null,
      canUndo: overrides.status === "confirmed",
    },
    transfer: {
      direction: "source_to_counterparty",
      ordinaryOperationType: "expense",
      accounts: [
        {
          id: "c145935c-67c6-4bf6-a0ce-64e5d611cf47",
          name: "Накопительный счёт",
          currency: "RUB",
        },
      ],
      rawRowCandidates: [],
      existingOperationCandidates: [],
    },
    lifecycle: {
      allowedActions:
        overrides.status === "matched"
          ? ["mark_duplicate", "needs_review", "ignore"]
          : [],
    },
  };
}
