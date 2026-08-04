import { afterEach, describe, expect, it, vi } from "vitest";

import {
  changePassword,
  loadAccount,
  loadUserSessions,
  logout,
  revokeOtherUserSessions,
  revokeUserSession,
  updateAccount,
} from "./account-api";

const account = {
  id: "7d71f4c7-ea92-45d4-817a-a1d85d509d4c",
  email: "max@example.test",
  name: "Max",
};

describe("account API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads a workspace-independent profile", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(account))),
    );
    await expect(loadAccount()).resolves.toEqual({
      status: "success",
      account,
    });
  });

  it("updates name with CSRF", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(account)));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateAccount("Max", "csrf-token")).resolves.toEqual({
      status: "success",
      account,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/account",
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
      }),
    );
  });

  it("logs out through the authenticated API", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response(null, { status: 204 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(logout("csrf-token")).resolves.toEqual({ status: "success" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/session",
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
      }),
    );
  });

  it("changes password with CSRF and current credential", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse({ message: "Пароль изменён." })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      changePassword("old secure phrase", "new secure phrase", "csrf-token"),
    ).resolves.toEqual({ status: "success", message: "Пароль изменён." });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/account/password",
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
      }),
    );
  });

  it("loads and validates active sessions", async () => {
    const sessions = {
      items: [
        {
          id: "1cb3ec51-2516-43c8-8d33-fad3f1164293",
          isCurrent: true,
          deviceSummary: "Chrome · Linux",
          createdAt: "2026-08-04T10:00:00Z",
          lastSeenAt: "2026-08-04T12:00:00Z",
          expiresAt: "2026-08-18T10:00:00Z",
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(sessions))),
    );

    await expect(loadUserSessions()).resolves.toEqual({
      status: "success",
      sessions: sessions.items,
    });
  });

  it("revokes one or all other sessions with CSRF", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(jsonResponse({ revokedCount: 2 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      revokeUserSession("session-id", "csrf-token"),
    ).resolves.toEqual({ status: "success" });
    await expect(revokeOtherUserSessions("csrf-token")).resolves.toEqual({
      status: "success",
      revokedCount: 2,
    });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/account/sessions/session-id",
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
      }),
    );
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
