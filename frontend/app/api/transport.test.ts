import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  parseApiError,
  requestJson,
  restoreAccessToken,
  setAccessToken,
} from "./transport";

describe("API transport", () => {
  beforeEach(() => {
    setAccessToken(null);
    vi.restoreAllMocks();
  });

  it("applies the same-origin JSON request policy", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response('{"value":42}'));

    const result = await requestJson("/api/v1/example", {
      headers: { "X-CSRF-Token": "csrf" },
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/example", {
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-CSRF-Token": "csrf",
      },
    });
    expect(result).toEqual({
      status: "response",
      body: { value: 42 },
      httpStatus: 200,
      ok: true,
    });
  });

  it("keeps a non-JSON server response distinct from a network failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>failure</html>", { status: 500 }),
    );

    await expect(requestJson("/api/v1/example")).resolves.toEqual({
      status: "response",
      body: null,
      httpStatus: 500,
      ok: false,
    });
  });

  it("refreshes once and retries an unauthorized request with Bearer auth", async () => {
    setAccessToken("expired");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(
          '{"accessToken":"fresh","expiresIn":900,"tokenType":"Bearer"}',
        ),
      )
      .mockResolvedValueOnce(new Response('{"value":42}'));

    await expect(requestJson("/api/v1/example")).resolves.toMatchObject({
      status: "response",
      ok: true,
    });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      headers: {
        Accept: "application/json",
        Authorization: "Bearer fresh",
      },
    });
  });

  it("uses one refresh for simultaneous unauthorized requests", async () => {
    setAccessToken("expired");
    let protectedCalls = 0;
    let refreshCalls = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (input === "/api/v1/auth/refresh") {
        refreshCalls += 1;
        return new Response(
          '{"accessToken":"fresh","expiresIn":900,"tokenType":"Bearer"}',
        );
      }
      protectedCalls += 1;
      return protectedCalls <= 2
        ? new Response(null, { status: 401 })
        : new Response('{"ok":true}');
    });

    const results = await Promise.all([
      requestJson("/api/v1/first"),
      requestJson("/api/v1/second"),
    ]);

    expect(
      results.every((result) => result.status === "response" && result.ok),
    ).toBe(true);
    expect(refreshCalls).toBe(1);
    expect(protectedCalls).toBe(4);
  });

  it("restores the in-memory access token from the refresh cookie", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          '{"accessToken":"restored","expiresIn":900,"tokenType":"Bearer"}',
        ),
      );

    await expect(restoreAccessToken()).resolves.toBe(true);
    await requestJson("/api/v1/session");

    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      headers: {
        Accept: "application/json",
        Authorization: "Bearer restored",
      },
    });
  });

  it("parses the shared API error envelope", () => {
    expect(
      parseApiError({
        error: {
          code: "validation_error",
          message: "Проверьте данные.",
          fieldErrors: { amount: ["Введите сумму."] },
        },
      }),
    ).toEqual({
      code: "validation_error",
      message: "Проверьте данные.",
      fieldErrors: { amount: ["Введите сумму."] },
    });
    expect(parseApiError({ detail: "not the API contract" })).toBeNull();
  });
});
