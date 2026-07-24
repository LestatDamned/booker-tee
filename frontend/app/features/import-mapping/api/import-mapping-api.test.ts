import { afterEach, describe, expect, it, vi } from "vitest";

import { loadImportMapping, previewImportMapping } from "./import-mapping-api";
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
});
