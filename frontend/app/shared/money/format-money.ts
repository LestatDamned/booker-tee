type FinancialOperationType = "income" | "expense" | "transfer" | "adjustment";

export function formatMoneyAmount(
  decimal: string,
  operationType: FinancialOperationType,
): string {
  const match = /^(\d+)(?:\.(\d+))?$/.exec(decimal);
  if (!match) {
    return decimal;
  }

  const integerPart = match[1];
  if (!integerPart) {
    return decimal;
  }
  const integer = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const fraction = (match[2] ?? "").padEnd(2, "0").slice(0, 2);
  const sign =
    operationType === "income" ? "+" : operationType === "expense" ? "−" : "";
  return `${sign}${integer},${fraction}`;
}
