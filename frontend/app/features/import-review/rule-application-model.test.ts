import { describe, expect, it } from "vitest";

import {
  ruleApplicationFailure,
  ruleApplicationMessage,
} from "./rule-application-model";

describe("rule application model", () => {
  it("formats successful application counts", () => {
    expect(ruleApplicationMessage({ checkedCount: 3, suggestedCount: 2 })).toBe(
      "Проверено строк: 3. Предложений применено: 2.",
    );
    expect(ruleApplicationMessage({ checkedCount: 0, suggestedCount: 0 })).toBe(
      "Нет строк, к которым можно применить правила.",
    );
  });

  it("does not offer retry for a forbidden action", () => {
    expect(ruleApplicationFailure({ status: "forbidden" })).toEqual({
      canRetry: false,
      message: "Недостаточно прав для применения правил.",
    });
    expect(
      ruleApplicationFailure({ status: "error", message: "Offline" }),
    ).toEqual({ canRetry: true, message: "Offline" });
  });
});
