import { afterEach, describe, expect, it, vi } from "vitest";

import {
  loadAuthConfig,
  login,
  requestPasswordReset,
  resetPassword,
  resendEmailVerification,
  signup,
} from "./auth-api";

describe("auth API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads signup availability", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            registrationMode: "invite_only",
            passwordMinLength: 12,
          }),
        ),
      ),
    );

    await expect(loadAuthConfig()).resolves.toEqual({
      status: "success",
      registrationMode: "invite_only",
      passwordMinLength: 12,
    });
  });

  it("posts login JSON and returns the safe continuation", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse({ nextPath: "/app/workspaces" })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      login({
        email: "max@example.test",
        password: "password",
        nextPath: "/app/profile",
      }),
    ).resolves.toEqual({ status: "success", nextPath: "/app/workspaces" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/login",
      expect.objectContaining({
        credentials: "same-origin",
        method: "POST",
        body: JSON.stringify({
          email: "max@example.test",
          password: "password",
          nextPath: "/app/profile",
        }),
      }),
    );
  });

  it("preserves signup field errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: "validation_error",
                message: "Проверьте переданные данные.",
                fieldErrors: { password: ["Пароль слишком короткий."] },
              },
            },
            422,
          ),
        ),
      ),
    );

    await expect(
      signup({ email: "max@example.test", password: "short" }),
    ).resolves.toEqual({
      status: "error",
      fieldErrors: { password: "Пароль слишком короткий." },
      message: "Проверьте переданные данные.",
    });
  });

  it("returns the generic signup accepted state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              message: "Если адрес подходит, письмо отправлено.",
              retryAfterSeconds: 60,
            },
            202,
          ),
        ),
      ),
    );

    await expect(
      signup({
        email: "max@example.test",
        password: "correct horse battery staple",
      }),
    ).resolves.toEqual({
      status: "success",
      message: "Если адрес подходит, письмо отправлено.",
      retryAfterSeconds: 60,
    });
  });

  it("preserves verification resend cooldown after throttling", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: "auth_rate_limited",
                message: "Повторите позже.",
                details: { retryAfterSeconds: 45 },
              },
            },
            429,
          ),
        ),
      ),
    );

    await expect(
      resendEmailVerification({ email: "max@example.test" }),
    ).resolves.toEqual({
      status: "error",
      fieldErrors: {},
      message: "Повторите позже.",
      retryAfterSeconds: 45,
    });
  });

  it("requests password reset without exposing account state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              message: "Если аккаунт существует, письмо отправлено.",
              retryAfterSeconds: 60,
            },
            202,
          ),
        ),
      ),
    );

    await expect(
      requestPasswordReset({ email: "max@example.test" }),
    ).resolves.toEqual({
      status: "success",
      message: "Если аккаунт существует, письмо отправлено.",
      retryAfterSeconds: 60,
    });
  });

  it("resets password through the single-use token endpoint", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(jsonResponse({ message: "Пароль изменён." })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      resetPassword({
        token: "opaque-token",
        newPassword: "new secure phrase",
      }),
    ).resolves.toEqual({ status: "success", message: "Пароль изменён." });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/password-resets",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          token: "opaque-token",
          newPassword: "new secure phrase",
        }),
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
