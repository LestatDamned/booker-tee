import { afterEach, describe, expect, it, vi } from "vitest";

import {
  bindTelegramDevLink,
  loadTelegramDevLinkConfig,
} from "./telegram-dev-link-api";

describe("Telegram dev-link API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads dev availability and binds with CSRF", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ enabled: true }))
      .mockResolvedValueOnce(jsonResponse({ bound: true }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadTelegramDevLinkConfig()).resolves.toEqual({
      status: "success",
    });
    await expect(
      bindTelegramDevLink({
        csrfToken: "csrf",
        displayName: "Max",
        externalUserId: "42",
      }),
    ).resolves.toEqual({ status: "success" });
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/v1/chat-integrations/telegram/dev-link",
      expect.objectContaining({
        body: JSON.stringify({ externalUserId: "42", displayName: "Max" }),
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf" }),
        method: "POST",
      }),
    );
  });

  it("keeps the production 404 as an unavailable route", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse({}, 404))),
    );

    await expect(loadTelegramDevLinkConfig()).resolves.toEqual({
      status: "not_found",
    });
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
