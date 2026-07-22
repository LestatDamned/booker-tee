import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyRulesToImportReview,
  confirmImportReviewItem,
  createImportReviewCategory,
  evaluateImportReviewDraft,
  postImportReviewTransfer,
  updateImportReviewLifecycle,
  undoImportReviewPosting,
} from "./import-review-mutations";
import { confirmedOperationId, importReviewPayload } from "../test-support";

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
              ruleName: null,
              pattern: null,
              operationType: null,
              categoryId: null,
              propertyId: null,
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

  it("sends expected status with a typed lifecycle action", async () => {
    const review = importReviewPayload();
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            itemId,
            documentId,
            replayed: false,
            review,
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await updateImportReviewLifecycle(
      documentId,
      itemId,
      { action: "mark_unique", expectedStatus: "possible_duplicate" },
      "csrf-token",
    );

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/import-review/${documentId}/items/${itemId}/lifecycle`,
      expect.objectContaining({
        body: JSON.stringify({
          action: "mark_unique",
          expectedStatus: "possible_duplicate",
        }),
      }),
    );
  });

  it("sends confirm with expected status and idempotency key", async () => {
    const review = importReviewPayload();
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            primaryDocumentId: documentId,
            itemId,
            operationId: confirmedOperationId,
            updatedItemIds: [itemId],
            replayed: false,
            reviews: [review],
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await confirmImportReviewItem(
      documentId,
      itemId,
      {
        operationType: "expense",
        categoryId,
        propertyId: null,
        expectedStatus: "matched",
        rememberRule: false,
        rulePattern: null,
      },
      "csrf-token",
      "cd66599a-3db7-46d8-b8f7-c463a2a0fd01",
    );

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/import-review/${documentId}/items/${itemId}/confirm`,
      expect.objectContaining({
        headers: expect.objectContaining({
          "Idempotency-Key": "cd66599a-3db7-46d8-b8f7-c463a2a0fd01",
        }),
        body: JSON.stringify({
          operationType: "expense",
          categoryId,
          propertyId: null,
          expectedStatus: "matched",
          rememberRule: false,
          rulePattern: null,
        }),
      }),
    );
  });

  it("sends the expected linked operation when undoing posting", async () => {
    const review = importReviewPayload();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              primaryDocumentId: documentId,
              itemId,
              operationId: confirmedOperationId,
              updatedItemIds: [itemId],
              replayed: false,
              reviews: [review],
            }),
            { status: 200 },
          ),
        ),
      ),
    );

    const result = await undoImportReviewPosting(
      documentId,
      itemId,
      { expectedOperationId: confirmedOperationId },
      "csrf-token",
    );

    expect(result.status).toBe("success");
    expect(fetch).toHaveBeenCalledWith(
      `/api/v1/import-review/${documentId}/items/${itemId}/undo-posting`,
      expect.objectContaining({
        body: JSON.stringify({ expectedOperationId: confirmedOperationId }),
      }),
    );
  });

  it("applies rules and validates the committed review snapshot", async () => {
    const review = importReviewPayload();
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            documentId,
            checkedCount: 1,
            suggestedCount: 1,
            updatedItemIds: [itemId],
            review,
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await applyRulesToImportReview(documentId, "csrf-token");

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/import-review/${documentId}/apply-rules`,
      expect.objectContaining({ body: "{}" }),
    );
  });
});

const documentId = "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8";
const itemId = "cb1b2959-b134-4a57-b2f4-7a7dfe8e8a42";
const categoryId = "078d4cda-d476-4bd6-b731-92d423d07c39";
