type FinancialOperationType = "income" | "expense" | "transfer" | "adjustment";

export type DecimalSign = -1 | 0 | 1;

const DECIMAL_PATTERN = /^([+-]?)(\d+)(?:[.,](\d+))?$/;
const NON_BREAKING_SPACE = "\u00a0";

export function decimalSign(decimal: string): DecimalSign | null {
  const match = DECIMAL_PATTERN.exec(decimal);
  if (!match) return null;

  const magnitude = `${match[2] ?? ""}${match[3] ?? ""}`;
  if (/^0+$/.test(magnitude)) return 0;
  return match[1] === "-" ? -1 : 1;
}

export function formatMoneyAmount(
  decimal: string,
  operationType: FinancialOperationType | null,
): string {
  const match = DECIMAL_PATTERN.exec(decimal);
  if (!match) {
    return decimal;
  }

  const integerPart = match[2];
  if (!integerPart) {
    return decimal;
  }
  const integer = integerPart.replace(
    /\B(?=(\d{3})+(?!\d))/g,
    NON_BREAKING_SPACE,
  );
  const fraction = (match[3] ?? "").padEnd(2, "0");
  const sourceSign = match[1] ?? "";
  const sign =
    operationType === "income"
      ? "+"
      : operationType === "expense"
        ? "−"
        : sourceSign === "-"
          ? "−"
          : sourceSign;
  return `${sign}${integer},${fraction}`;
}

export function formatMoneyWithCurrency(
  decimal: string,
  currency: string,
): string {
  return `${formatMoneyAmount(decimal, null)}${NON_BREAKING_SPACE}${currencySymbol(currency)}`;
}

function currencySymbol(currency: string): string {
  try {
    return (
      new Intl.NumberFormat("ru-RU", {
        currency,
        currencyDisplay: "narrowSymbol",
        style: "currency",
      })
        .formatToParts(0)
        .find((part) => part.type === "currency")?.value ?? currency
    );
  } catch {
    return currency;
  }
}
