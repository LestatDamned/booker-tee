import { afterEach, describe, expect, it, vi } from "vitest";

import { issueTelegramLinkCode } from "./telegram-dev-link-api";

describe("Telegram link API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("issues a one-time code with CSRF", async () => {
    const payload = {
      command: "/link workspace.secret",
      expiresAt: "2026-08-29T07:10:00Z",
    };
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(payload)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(issueTelegramLinkCode("csrf")).resolves.toEqual({
      status: "success",
      linkCode: payload,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/chat-integrations/telegram/link-code",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf" }),
        method: "POST",
      }),
    );
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
