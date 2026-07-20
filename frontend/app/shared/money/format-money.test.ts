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
});
