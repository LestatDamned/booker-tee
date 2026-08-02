import { afterEach, describe, expect, it, vi } from "vitest";

import { directory } from "../test-support";
import {
  createTransactionRule,
  changeTransactionRuleLifecycle,
  deleteTransactionRule,
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

  it("changes lifecycle with stale guards and maps activation blocker details", async () => {
    const changed = { ...directory.items[0]!, isActive: false };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          item: changed,
          impact: {
            futureMatchingChanged: true,
            existingSuggestionsChanged: false,
            existingSuggestionCount: 4,
          },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "transaction_rule_activation_blocked",
              message: "Category unavailable.",
              details: { blockedReasonCode: "category_inactive" },
            },
          },
          422,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      changeTransactionRuleLifecycle(directory.items[0]!, "disable", "csrf"),
    ).resolves.toEqual({
      status: "success",
      value: {
        item: changed,
        impact: {
          futureMatchingChanged: true,
          existingSuggestionsChanged: false,
          existingSuggestionCount: 4,
        },
      },
    });
    const request = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(JSON.parse(String(request.body))).toEqual({
      expectedActive: true,
      expectedUpdatedAt: "2026-08-02T09:00:00Z",
    });
    await expect(
      changeTransactionRuleLifecycle(changed, "enable", "csrf"),
    ).resolves.toEqual({
      status: "blocked",
      blockedReasonCode: "category_inactive",
      message: "Category unavailable.",
    });
  });

  it("deletes with stale guards and preserves typed provenance blockers", async () => {
    const item = {
      ...directory.items[0]!,
      isActive: false,
      capabilities: {
        ...directory.items[0]!.capabilities,
        canDelete: true,
      },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ deletedId: item.id, name: item.name }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "transaction_rule_delete_blocked",
              message: "Правило используется в истории импорта.",
              details: {
                blockedReasonCode: "raw_suggestions",
                directRawSuggestionCount: 4,
              },
            },
          },
          409,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteTransactionRule(item, "csrf")).resolves.toEqual({
      status: "success",
      value: { deletedId: item.id, name: item.name },
    });
    expect(fetchMock.mock.calls[0]![0]).toBe(
      `/api/v1/transaction-rules/${item.id}`,
    );
    const request = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(request.method).toBe("DELETE");
    expect(JSON.parse(String(request.body))).toEqual({
      expectedActive: false,
      expectedUpdatedAt: item.updatedAt,
    });
    await expect(deleteTransactionRule(item, "csrf")).resolves.toEqual({
      status: "blocked",
      blockedReasonCode: "raw_suggestions",
      directRawSuggestionCount: 4,
      message: "Правило используется в истории импорта.",
    });
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
