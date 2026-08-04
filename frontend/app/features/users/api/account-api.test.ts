import { afterEach, describe, expect, it, vi } from "vitest";

import { loadAccount, logout, updateAccount } from "./account-api";

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
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
