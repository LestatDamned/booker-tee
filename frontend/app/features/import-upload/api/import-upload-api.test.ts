import { afterEach, describe, expect, it, vi } from "vitest";

import {
  loadImportUploadReference,
  uploadImportDocument,
} from "./import-upload-api";

describe("import upload API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps reference auth, permission and transport failures distinct", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 403 }))
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadImportUploadReference()).resolves.toEqual({
      status: "unauthenticated",
    });
    await expect(loadImportUploadReference()).resolves.toEqual({
      status: "forbidden",
    });
    await expect(loadImportUploadReference()).resolves.toEqual({
      status: "error",
      message: "Backend недоступен.",
    });
    await expect(loadImportUploadReference()).resolves.toEqual({
      status: "error",
      message: "API вернул статус 503.",
    });
  });

  it("uses the shared unauthenticated contract for upload mutations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 401 }))),
    );

    await expect(
      uploadImportDocument({
        accountId: "account-id",
        csrfToken: "csrf",
        file: new File(["statement"], "statement.pdf"),
        idempotencyKey: "retry-key",
      }),
    ).resolves.toEqual({ status: "unauthenticated" });
  });
});
