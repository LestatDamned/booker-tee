type FinancialOperationType = "income" | "expense" | "transfer" | "adjustment";

export function formatMoneyAmount(
  decimal: string,
  operationType: FinancialOperationType | null,
): string {
  const normalized = decimal.replace(",", ".");
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(normalized);
  if (!match) {
    return decimal;
  }

  const integerPart = match[2];
  if (!integerPart) {
    return decimal;
  }
  const integer = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const fraction = (match[3] ?? "").padEnd(2, "0").slice(0, 2);
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
