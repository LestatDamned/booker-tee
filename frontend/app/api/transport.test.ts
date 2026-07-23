import { describe, expect, it, vi } from "vitest";

import { parseApiError, requestJson } from "./transport";

describe("API transport", () => {
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
