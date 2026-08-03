import { describe, expect, it } from "vitest";

import {
  expenseCategoryId,
  importReviewPayload,
  propertyId,
  remainingItemId,
} from "./test-support";
import {
  buildPostingConfirmationRequest,
  confirmedPostingSelection,
  normalizedRulePattern,
  postingError,
  postingSelectionFingerprint,
} from "./posting-model";

describe("posting model", () => {
  it("exposes only a committed and confirmable income or expense selection", () => {
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("review item fixture is required");
    item.selection = { categoryId: expenseCategoryId, propertyId };
    item.confirmability = { canConfirm: true, blockingReasonCodes: [] };
    const evaluation = {
      itemId: item.id,
      classification: item.classification,
      selection: item.selection,
      confirmability: item.confirmability,
      ruleSuggestion: item.ruleSuggestion,
    };

    expect(confirmedPostingSelection(false, evaluation)).toEqual({
      categoryId: expenseCategoryId,
      operationType: "expense",
      propertyId,
    });
    expect(confirmedPostingSelection(true, evaluation)).toBeNull();
  });

  it("normalizes the optional rule exactly once when building the request", () => {
    const selection = {
      categoryId: expenseCategoryId,
      operationType: "expense" as const,
      propertyId: null,
    };

    expect(normalizedRulePattern("  Магазин  ")).toEqual({
      cleanedRulePattern: "Магазин",
      rememberRule: true,
    });
    expect(
      buildPostingConfirmationRequest(selection, "matched", "  Магазин  "),
    ).toEqual({
      operationType: "expense",
      categoryId: expenseCategoryId,
      propertyId: null,
      expectedStatus: "matched",
      rememberRule: true,
      rulePattern: "Магазин",
    });
    expect(postingSelectionFingerprint(selection, " Магазин ")).toContain(
      ":Магазин",
    );
  });

  it("keeps failure copy explicit", () => {
    expect(postingError({ status: "forbidden" })).toContain(
      "Недостаточно прав",
    );
  });
});
