import { afterEach, describe, expect, it, vi } from "vitest";

import { loadProperties } from "./properties-api";

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
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
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
