import { describe, expect, it } from "vitest";

import { importReviewPayload, reviewDocumentId } from "./test-support";
import { reviewForDocument } from "./review-reconciliation";

describe("review reconciliation", () => {
  it("selects the authoritative review for the requested document", () => {
    const review = importReviewPayload();

    expect(reviewForDocument([review], reviewDocumentId)).toBe(review);
    expect(reviewForDocument([review], crypto.randomUUID())).toBeUndefined();
  });
});
