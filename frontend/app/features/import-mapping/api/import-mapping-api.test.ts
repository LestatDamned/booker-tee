import { afterEach, describe, expect, it, vi } from "vitest";

import {
  commitImportMapping,
  loadImportMapping,
  loadImportMappingSourceRows,
  previewImportMapping,
} from "./import-mapping-api";
import {
  importMappingPayload,
  importMappingPreview,
  mappingDocumentId,
} from "../test-support";

describe("import mapping API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("validates the mapping read model", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(importMappingPayload()), { status: 200 }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadImportMapping(mappingDocumentId)).resolves.toMatchObject({
      status: "success",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/imports/documents/${mappingDocumentId}/mapping`,
      {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      },
    );
  });

  it("sends mapping to preview with CSRF", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(importMappingPreview()), { status: 200 }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const command = importMappingPayload().defaultMapping;

    await expect(
      previewImportMapping({
        command,
        csrfToken: "csrf-token",
        documentId: mappingDocumentId,
      }),
    ).resolves.toMatchObject({ status: "success" });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/imports/documents/${mappingDocumentId}/mapping/preview`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-CSRF-Token": "csrf-token",
        }),
        body: JSON.stringify({ mapping: command }),
      }),
    );
  });

  it("loads a bounded source-row window", async () => {
    const source = {
      tableRef: { pageNumber: 2, tableIndex: 0 },
      rows: [{ rowNumber: 31, cells: ["31.07.2026", "Операция"] }],
      totalRowCount: 80,
      startRowNumber: 31,
      rowLimit: 30,
      hasPrevious: true,
      hasNext: true,
    };
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(source), { status: 200 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      loadImportMappingSourceRows({
        documentId: mappingDocumentId,
        startRowNumber: 31,
        tableRef: source.tableRef,
      }),
    ).resolves.toEqual({ status: "success", source });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/imports/documents/${mappingDocumentId}/mapping/tables/2/0/rows?startRowNumber=31&rowLimit=30`,
      {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      },
    );
  });

  it("keeps typed field errors from preview validation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "invalid_mapping",
                message: "Проверьте выбранные колонки.",
                fieldErrors: {
                  operationDateColumn: ["Колонка даты не подходит."],
                },
              },
            }),
            { status: 422 },
          ),
        ),
      ),
    );

    await expect(
      previewImportMapping({
        command: importMappingPayload().defaultMapping,
        csrfToken: "csrf-token",
        documentId: mappingDocumentId,
      }),
    ).resolves.toEqual({
      status: "validation_error",
      message: "Проверьте выбранные колонки.",
      fieldErrors: {
        operationDateColumn: ["Колонка даты не подходит."],
      },
    });
  });

  it("commits mapping with CSRF and idempotency key", async () => {
    const result = {
      documentId: mappingDocumentId,
      status: "requires_review",
      importedRowCount: 2,
      templateId: null,
      replayed: false,
      reviewTarget: {
        kind: "import_review",
        documentId: mappingDocumentId,
      },
    };
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(result), { status: 200 })),
    );
    vi.stubGlobal("fetch", fetchMock);
    const command = importMappingPayload().defaultMapping;

    await expect(
      commitImportMapping({
        command,
        csrfToken: "csrf-token",
        documentId: mappingDocumentId,
        idempotencyKey: "8be554fa-970b-45b7-95b2-7c4af8324b65",
        templateName: "Экспобанк",
      }),
    ).resolves.toMatchObject({ status: "success" });
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/imports/documents/${mappingDocumentId}/mapping/import`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Idempotency-Key": "8be554fa-970b-45b7-95b2-7c4af8324b65",
          "X-CSRF-Token": "csrf-token",
        }),
        body: JSON.stringify({
          mapping: command,
          templateName: "Экспобанк",
        }),
      }),
    );
  });
});
