import { describe, expect, it } from "vitest";

import {
  decimalSign,
  formatMoneyAmount,
  formatMoneyWithCurrency,
} from "./format-money";

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

  it("preserves precision instead of truncating or rounding decimals", () => {
    expect(formatMoneyAmount("0.001", null)).toBe("0,001");
    expect(formatMoneyAmount("999999999999999999999999.1234", null)).toBe(
      "999 999 999 999 999 999 999 999,1234",
    );
  });

  it("formats a currency symbol without converting the decimal to Number", () => {
    expect(formatMoneyWithCurrency("1234.567", "RUB")).toBe("1 234,567 ₽");
    expect(formatMoneyWithCurrency("1234.567", "UNKNOWN")).toBe(
      "1 234,567 UNKNOWN",
    );
  });

  it("returns malformed source values unchanged", () => {
    expect(formatMoneyAmount("not-a-number", null)).toBe("not-a-number");
  });
});

describe("decimalSign", () => {
  it("reads the sign from exact decimal strings", () => {
    expect(decimalSign("999999999999999999999999.0001")).toBe(1);
    expect(decimalSign("-0.0001")).toBe(-1);
    expect(decimalSign("-0.0000")).toBe(0);
    expect(decimalSign("+0,00")).toBe(0);
  });

  it("rejects malformed decimal strings", () => {
    expect(decimalSign("1 000,00")).toBeNull();
    expect(decimalSign("not-a-number")).toBeNull();
  });
});
