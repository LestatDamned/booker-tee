import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  parseApiError,
  requestBlob,
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

  it("loads protected binary content with Bearer auth", async () => {
    setAccessToken("binary-token");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("png", { status: 200 }));

    const result = await requestBlob("/api/v1/protected-image");

    expect(result).toMatchObject({
      status: "response",
      ok: true,
      httpStatus: 200,
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/protected-image", {
      credentials: "same-origin",
      headers: { Authorization: "Bearer binary-token" },
    });
  });

  it("waits for a concurrent JSON refresh before loading protected binary content", async () => {
    setAccessToken("expired");
    let releaseRefresh: () => void = () => undefined;
    const refreshGate = new Promise<void>((resolve) => {
      releaseRefresh = resolve;
    });
    let markRefreshStarted: () => void = () => undefined;
    const refreshStarted = new Promise<void>((resolve) => {
      markRefreshStarted = resolve;
    });
    let jsonCalls = 0;
    let blobCalls = 0;
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, options) => {
        if (input === "/api/v1/auth/refresh") {
          markRefreshStarted();
          await refreshGate;
          return new Response(
            '{"accessToken":"fresh","expiresIn":900,"tokenType":"Bearer"}',
          );
        }
        if (input === "/api/v1/example") {
          jsonCalls += 1;
          return jsonCalls === 1
            ? new Response(null, { status: 401 })
            : new Response('{"ok":true}');
        }
        blobCalls += 1;
        expect(options).toMatchObject({
          headers: { Authorization: "Bearer fresh" },
        });
        return new Response("png", { status: 200 });
      });

    const jsonResult = requestJson("/api/v1/example");
    await refreshStarted;
    const blobResult = requestBlob("/api/v1/protected-image");
    await Promise.resolve();
    expect(blobCalls).toBe(0);
    releaseRefresh();

    await expect(jsonResult).resolves.toMatchObject({
      status: "response",
      ok: true,
    });
    await expect(blobResult).resolves.toMatchObject({
      status: "response",
      ok: true,
      httpStatus: 200,
    });
    expect(blobCalls).toBe(1);
    expect(
      fetchMock.mock.calls.filter(
        ([input]) => input === "/api/v1/auth/refresh",
      ),
    ).toHaveLength(1);
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
