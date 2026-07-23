import { afterEach, describe, expect, it, vi } from "vitest";

import { loadImportDocuments } from "./import-documents-api";

describe("loadImportDocuments", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses the typed list response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(documentListPayload))),
    );

    const result = await loadImportDocuments();

    expect(result.status).toBe("success");
    if (result.status === "success") {
      expect(result.documents.items[0]?.nextStepKind).toBe("mapping");
    }
  });

  it("rejects an invalid server payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({ ...documentListPayload, items: [{ id: "broken" }] }),
        ),
      ),
    );

    await expect(loadImportDocuments()).resolves.toEqual({
      status: "error",
      message: "API вернул список документов неожиданного формата.",
    });
  });

  it("maps authentication and network failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response(null, { status: 401 }))
        .mockRejectedValueOnce(new TypeError("offline")),
    );

    await expect(loadImportDocuments()).resolves.toEqual({
      status: "unauthenticated",
    });
    await expect(loadImportDocuments()).resolves.toEqual({
      status: "error",
      message: "Backend недоступен.",
    });
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

const documentListPayload = {
  workspaceId: "c12c9ac8-6851-4467-b87a-da7fc70586c8",
  workspaceName: "Дом",
  items: [
    {
      id: "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8",
      filename: "statement.pdf",
      status: "requires_review",
      createdAt: "2026-07-24T10:00:00Z",
      fileSizeBytes: 2048,
      detectedBankName: "Альфа-Банк",
      statementPeriod: { start: "2026-07-01", end: "2026-07-31" },
      account: {
        id: "4958dd80-af47-4131-8f16-16c0ca04f63c",
        name: "Основной",
        currency: "RUB",
        bankName: "Альфа-Банк",
      },
      totalRowCount: 0,
      reviewableRowCount: 0,
      capabilities: {
        canOpenDetail: true,
        canMap: true,
        canReview: false,
      },
      nextStepKind: "mapping",
    },
  ],
  pagination: {
    page: 1,
    perPage: 25,
    total: 1,
    totalPages: 1,
    hasPrevious: false,
    hasNext: false,
  },
  filterOptions: {
    accounts: [
      {
        id: "4958dd80-af47-4131-8f16-16c0ca04f63c",
        name: "Основной",
        currency: "RUB",
        bankName: "Альфа-Банк",
      },
    ],
    perPage: [25, 50, 100],
  },
  summary: { totalDocumentCount: 1, attentionDocumentCount: 1 },
  capabilities: { canUpload: true, readonlyReasonCode: null },
};
