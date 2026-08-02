import { afterEach, describe, expect, it, vi } from "vitest";

import { directory } from "../test-support";
import {
  createTransactionRule,
  loadTransactionRuleForEdit,
  loadTransactionRules,
  seedDefaultTransactionRules,
  updateTransactionRule,
} from "./transaction-rules-api";

describe("transaction rules API adapter", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("validates the generated directory contract at runtime", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(directory)));
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadTransactionRules("?status=active&page=2");

    expect(result).toEqual({ status: "success", directory });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/transaction-rules?status=active&page=2",
      expect.anything(),
    );
  });

  it("rejects a malformed money projection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            ...directory,
            items: [
              {
                ...directory.items[0],
                condition: { ...directory.items[0]!.condition, amountMin: 100 },
              },
            ],
          }),
        ),
      ),
    );

    await expect(loadTransactionRules("")).resolves.toEqual({
      status: "error",
      message: "API вернул список правил неожиданного формата.",
    });
  });

  it("sends create CSRF and idempotency headers and validates the response", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        jsonResponse({ item: directory.items[0], replayed: false }, 201),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await createTransactionRule(
      {
        name: null,
        pattern: "OZON",
        matchType: "contains",
        direction: "outflow",
        amountMin: "100.00",
        amountMax: null,
        operationType: "expense",
        categoryId: null,
        propertyId: null,
        applicationMode: "suggest",
      },
      { csrfToken: "csrf", idempotencyKey: "retry-key" },
    );

    expect(result.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/transaction-rules",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Idempotency-Key": "retry-key",
          "X-CSRF-Token": "csrf",
        }),
      }),
    );
  });

  it("maps seed counts and mutation validation errors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          createdRules: 2,
          existingRules: 51,
          createdCategories: 0,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "transaction_rule_validation_error",
              message: "Pattern is invalid.",
              fieldErrors: { pattern: ["Pattern is invalid."] },
            },
          },
          422,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(seedDefaultTransactionRules("csrf")).resolves.toEqual({
      status: "success",
      value: { createdRules: 2, existingRules: 51, createdCategories: 0 },
    });
    const invalid = await createTransactionRule({} as never, {
      csrfToken: "csrf",
      idempotencyKey: "key",
    });
    expect(invalid).toEqual({
      status: "validation_error",
      fieldErrors: { pattern: ["Pattern is invalid."] },
      message: "Pattern is invalid.",
    });
  });

  it("loads an authoritative edit snapshot and sends its expected version", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          item: directory.items[0],
          references: directory.references,
        }),
      )
      .mockResolvedValueOnce(jsonResponse(directory.items[0]));
    vi.stubGlobal("fetch", fetchMock);
    const loaded = await loadTransactionRuleForEdit(directory.items[0]!.id);
    expect(loaded.status).toBe("success");
    await updateTransactionRule(
      directory.items[0]!.id,
      {
        name: null,
        pattern: "OZON",
        matchType: "contains",
        direction: "outflow",
        amountMin: null,
        amountMax: null,
        operationType: "expense",
        categoryId: null,
        propertyId: null,
        applicationMode: "suggest",
        expectedUpdatedAt: directory.items[0]!.updatedAt,
      },
      "csrf",
    );
    expect(fetchMock.mock.calls[1]![0]).toBe(
      `/api/v1/transaction-rules/${directory.items[0]!.id}`,
    );
    expect(fetchMock.mock.calls[1]![1]).toEqual(
      expect.objectContaining({
        method: "PUT",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf" }),
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
