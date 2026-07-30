import { afterEach, describe, expect, it, vi } from "vitest";

import { createAccount, loadAccounts } from "./accounts-api";

describe("accounts API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("validates the account directory at the network boundary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(directoryPayload))),
    );

    const result = await loadAccounts();

    expect(result.status).toBe("success");
    if (result.status === "success") {
      expect(result.directory.items[0]?.balance).toBe("9118.88");
    }
  });

  it("rejects a malformed account directory", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(jsonResponse({ ...directoryPayload, items: [{}] })),
      ),
    );

    await expect(loadAccounts()).resolves.toEqual({
      status: "error",
      message: "API вернул список счетов неожиданного формата.",
    });
  });

  it("keeps stable server field errors for create", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: "validation_error",
                message: "Проверьте переданные данные.",
                fieldErrors: { name: ["Название счета обязательно."] },
              },
            },
            422,
          ),
        ),
      ),
    );

    const result = await createAccount({
      csrfToken: "csrf-token",
      draft: {
        name: "",
        accountType: "card",
        currency: "RUB",
        initialBalance: "0.00",
      },
    });

    expect(result).toEqual({
      status: "error",
      code: "validation_error",
      message: "Проверьте переданные данные.",
      fieldErrors: { name: ["Название счета обязательно."] },
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
      name: "Основной",
      accountType: "card",
      currency: "RUB",
      initialBalance: "10000.00",
      balance: "9118.88",
      balanceDirection: "positive",
      movementCount: 4,
      isActive: true,
      updatedAt: "2026-07-30T12:00:00Z",
      capabilities: { canArchive: true, canRestore: false },
    },
  ],
  accountTypes: ["cash", "card", "deposit", "checking", "other"],
  capabilities: { canCreate: true, readonlyReasonCode: null },
};
