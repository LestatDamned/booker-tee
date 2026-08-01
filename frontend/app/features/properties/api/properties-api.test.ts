import { afterEach, describe, expect, it, vi } from "vitest";

import { createProperty, loadProperties } from "./properties-api";

describe("Properties API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("validates the directory response at the network boundary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(directoryPayload))),
    );

    const result = await loadProperties();

    expect(result).toEqual({
      status: "success",
      directory: directoryPayload,
    });
  });

  it("rejects a lifecycle status outside the accepted contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...directoryPayload,
            items: [{ ...directoryPayload.items[0], status: "inactive" }],
          }),
        ),
      ),
    );

    const result = await loadProperties();

    expect(result).toEqual({
      status: "error",
      message: "API вернул список объектов неожиданного формата.",
    });
  });

  it("returns an unauthenticated state for an expired session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 401 }))),
    );

    await expect(loadProperties()).resolves.toEqual({
      status: "unauthenticated",
    });
  });

  it("keeps network and HTTP failures recoverable", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadProperties()).resolves.toEqual({
      status: "error",
      message: "Backend недоступен.",
    });
    await expect(loadProperties()).resolves.toEqual({
      status: "error",
      message: "API вернул статус 503.",
    });
  });

  it("creates a property with CSRF and validates the committed response", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse(directoryPayload.items[0], 201)),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await createProperty({
      csrfToken: "csrf-token",
      draft: { name: "Квартира", shortName: "Дом", address: "Мира, 1" },
    });

    expect(result).toEqual({
      status: "success",
      property: directoryPayload.items[0],
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/properties",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Квартира",
          shortName: "Дом",
          address: "Мира, 1",
        }),
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
      }),
    );
  });

  it("preserves server field errors for the create form", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: "validation_error",
                message: "Проверьте переданные данные.",
                fieldErrors: { name: ["Название объекта обязательно."] },
              },
            },
            422,
          ),
        ),
      ),
    );

    await expect(
      createProperty({
        csrfToken: "csrf-token",
        draft: { name: "", shortName: "", address: "" },
      }),
    ).resolves.toEqual({
      status: "error",
      code: "validation_error",
      message: "Проверьте переданные данные.",
      fieldErrors: { name: ["Название объекта обязательно."] },
    });
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

const directoryPayload = {
  items: [
    {
      id: "285c18d8-78bb-46d7-b6cd-d6fc897ab8a2",
      name: "Квартира",
      shortName: "Дом",
      address: "Красноярск, ул. Мира, 1",
      status: "active",
      archivedAt: null,
      updatedAt: "2026-08-01T08:30:00Z",
      capabilities: {
        canUpdate: true,
        canArchive: true,
        canRestore: false,
      },
    },
  ],
  capabilities: { canCreate: true, readonlyReasonCode: null },
} as const;
