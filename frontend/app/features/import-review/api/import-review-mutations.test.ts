import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createImportReviewCategory,
  evaluateImportReviewDraft,
  postImportReviewTransfer,
} from "./import-review-mutations";
import { importReviewPayload } from "../test-support";

describe("import review mutations", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends a draft for server evaluation with CSRF", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            itemId: itemId,
            classification: { operationType: "expense", source: "explicit" },
            selection: { categoryId, propertyId: null },
            confirmability: { canConfirm: true, blockingReasonCodes: [] },
            ruleSuggestion: {
              isActive: false,
              wasAutoApplied: false,
              ruleId: null,
            },
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await evaluateImportReviewDraft(
      documentId,
      itemId,
      { operationType: "expense", categoryId, propertyId: null },
      "csrf-token",
    );

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/import-review/${documentId}/items/${itemId}/draft-evaluation`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
      }),
    );
  });

  it("keeps typed field errors from category creation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "invalid_category",
                message: "Категорию не удалось создать.",
                fieldErrors: { name: ["Название уже занято."] },
              },
            }),
            { status: 422 },
          ),
        ),
      ),
    );

    await expect(
      createImportReviewCategory(
        documentId,
        itemId,
        { name: "Продукты", kind: "expense" },
        "csrf-token",
      ),
    ).resolves.toEqual({
      status: "validation_error",
      message: "Категорию не удалось создать.",
      fieldErrors: { name: ["Название уже занято."] },
    });
  });

  it("sends a discriminated transfer command with a stable idempotency key", async () => {
    const review = importReviewPayload();
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            primaryDocumentId: documentId,
            updatedItemIds: [itemId],
            validationDocumentIds: [documentId],
            reviews: [review],
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await postImportReviewTransfer(
      documentId,
      itemId,
      { kind: "new_transfer", counterpartyAccountId: categoryId },
      "csrf-token",
      "cd66599a-3db7-46d8-b8f7-c463a2a0fd01",
    );

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/import-review/${documentId}/items/${itemId}/transfer`,
      expect.objectContaining({
        headers: expect.objectContaining({
          "Idempotency-Key": "cd66599a-3db7-46d8-b8f7-c463a2a0fd01",
          "X-CSRF-Token": "csrf-token",
        }),
        body: JSON.stringify({
          kind: "new_transfer",
          counterpartyAccountId: categoryId,
        }),
      }),
    );
  });
});

const documentId = "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8";
const itemId = "cb1b2959-b134-4a57-b2f4-7a7dfe8e8a42";
const categoryId = "078d4cda-d476-4bd6-b731-92d423d07c39";
