import { describe, expect, it } from "vitest";

import { importReviewPayload, remainingItemId } from "./test-support";
import {
  categoryMutationError,
  defaultCategoryKind,
  draftMutationError,
  ordinaryOperationLabel,
  parseCategoryKind,
  serverClassificationDraft,
  serverClassificationEvaluation,
} from "./classification-model";

describe("classification model", () => {
  it("derives the editable draft and committed evaluation from server facts", () => {
    const item = importReviewPayload().items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("review item fixture is required");

    expect(serverClassificationDraft(item)).toEqual({
      operationType: "expense",
      categoryId: null,
      propertyId: null,
    });
    expect(serverClassificationEvaluation(item)).toEqual({
      itemId: item.id,
      classification: item.classification,
      selection: item.selection,
      confirmability: item.confirmability,
      ruleSuggestion: item.ruleSuggestion,
    });
    expect(ordinaryOperationLabel(item)).toBe("Расход");
  });

  it("normalizes category kinds without inventing financial meaning", () => {
    expect(defaultCategoryKind("income")).toBe("income");
    expect(defaultCategoryKind("expense")).toBe("expense");
    expect(defaultCategoryKind(null)).toBe("mixed");
    expect(parseCategoryKind("adjustment")).toBe("adjustment");
    expect(parseCategoryKind("unknown")).toBe("mixed");
  });

  it("keeps recovery copy specific to the interrupted workflow", () => {
    expect(draftMutationError({ status: "unauthenticated" })).toContain(
      "draft сохранён",
    );
    expect(categoryMutationError({ status: "unauthenticated" })).toContain(
      "Название новой категории сохранено",
    );
  });
});
