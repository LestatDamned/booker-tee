import { describe, expect, it } from "vitest";

import { formatMoneyAmount } from "./format-money";

describe("formatMoneyAmount", () => {
  it("formats decimal strings without converting financial data to float", () => {
    expect(formatMoneyAmount("65000.00", "expense")).toBe("−65 000,00");
    expect(formatMoneyAmount("125000.5", "income")).toBe("+125 000,50");
  });

  it("uses operation semantics rather than the amount sign", () => {
    expect(formatMoneyAmount("65000.00", "transfer")).toBe("65 000,00");
  });

  it("preserves source signs when operation semantics do not override them", () => {
    expect(formatMoneyAmount("-65000,5", null)).toBe("−65 000,50");
    expect(formatMoneyAmount("+65000", "transfer")).toBe("+65 000,00");
  });

  it("returns malformed source values unchanged", () => {
    expect(formatMoneyAmount("not-a-number", null)).toBe("not-a-number");
  });
});
