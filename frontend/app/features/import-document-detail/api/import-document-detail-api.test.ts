import { afterEach, describe, expect, it, vi } from "vitest";

import {
  loadImportDocumentDetail,
  mutateImportDocument,
  type ImportDocumentDetailDto,
} from "./import-document-detail-api";

describe("import document detail API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps auth, permission, not-found and transport states distinct", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 403 }))
      .mockResolvedValueOnce(new Response(null, { status: 404 }))
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadImportDocumentDetail("document-id")).resolves.toEqual({
      status: "unauthenticated",
    });
    await expect(loadImportDocumentDetail("document-id")).resolves.toEqual({
      status: "forbidden",
    });
    await expect(loadImportDocumentDetail("document-id")).resolves.toEqual({
      status: "not_found",
    });
    await expect(loadImportDocumentDetail("document-id")).resolves.toEqual({
      status: "error",
      message: "Backend недоступен.",
    });
    await expect(loadImportDocumentDetail("document-id")).resolves.toEqual({
      status: "error",
      message: "API вернул статус 503.",
    });
  });

  it("preserves a domain conflict message for document mutations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "import_document_conflict",
                message: "Документ уже изменился.",
              },
            }),
            { status: 409 },
          ),
        ),
      ),
    );

    await expect(
      mutateImportDocument(documentSnapshot, "ignore", "csrf"),
    ).resolves.toEqual({
      status: "conflict",
      message: "Документ уже изменился.",
    });
  });
});

const documentSnapshot = {
  id: "document-id",
  status: "requires_review",
} as ImportDocumentDetailDto;
