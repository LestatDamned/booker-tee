import { describe, expect, it } from "vitest";

import { importReviewPayload, remainingItemId } from "./test-support";
import {
  transferDirectionLabel,
  transferFailure,
  transferRequest,
} from "./transfer-model";

describe("transfer model", () => {
  it("builds only explicit transfer commands", () => {
    expect(transferRequest("account:account-id")).toEqual({
      kind: "new_transfer",
      counterpartyAccountId: "account-id",
    });
    expect(transferRequest("raw:item-id")).toEqual({
      kind: "raw_row_match",
      matchedItemId: "item-id",
    });
    expect(transferRequest("operation:operation-id")).toEqual({
      kind: "existing_operation_link",
      operationId: "operation-id",
    });
    expect(transferRequest("unknown:value")).toBeNull();
  });

  it("presents direction from server-owned transfer facts", () => {
    const item = importReviewPayload().items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("review item fixture is required");

    expect(transferDirectionLabel(item, "")).toBe(
      "Основной счёт → Не выбран второй счёт",
    );
    expect(
      transferDirectionLabel(
        item,
        "account:c145935c-67c6-4bf6-a0ce-64e5d611cf47",
      ),
    ).toBe("Основной счёт → Накопительный счёт");
  });

  it("allows retry only for transport and unexpected failures", () => {
    expect(
      transferFailure({ status: "error", message: "Backend недоступен." }),
    ).toEqual({ canRetry: true, message: "Backend недоступен." });
    expect(
      transferFailure({ status: "conflict", message: "Строка изменилась." }),
    ).toEqual({
      canRetry: false,
      message: "Строка изменилась. Обновите выбор и попробуйте снова.",
    });
  });
});
