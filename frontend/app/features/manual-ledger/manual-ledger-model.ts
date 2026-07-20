import type { components } from "../../api/generated/schema";
import { formatMoneyAmount } from "../../shared/money/format-money";
import type { BadgeTone } from "../../ui/badge/badge";
import type { MoneyTone } from "../../ui/money-value/money-value";

type ManualOperationDto = components["schemas"]["ManualOperationResponse"];
type OperationType = components["schemas"]["OperationType"];
type OperationStatus = components["schemas"]["OperationStatus"];

export type ManualOperationRowModel = {
  id: string;
  anchorId: string;
  canCancel: boolean;
  canDelete: boolean;
  canEdit: boolean;
  canRestore: boolean;
  date: string;
  description: string;
  money: { amount: string; currency: string; tone: MoneyTone } | null;
  meta: string[];
  operationLabel: string;
  operationTone: BadgeTone;
  statusLabel: string;
  statusTone: BadgeTone;
  version: number;
};

const operationPresentation: Record<
  OperationType,
  { label: string; tone: BadgeTone }
> = {
  income: { label: "доход", tone: "income" },
  expense: { label: "расход", tone: "expense" },
  transfer: { label: "перевод", tone: "transfer" },
  adjustment: { label: "корректировка", tone: "adjustment" },
};

const statusPresentation: Record<
  OperationStatus,
  { label: string; tone: BadgeTone }
> = {
  draft: { label: "черновик", tone: "warning" },
  needs_review: { label: "нужна проверка", tone: "warning" },
  confirmed: { label: "подтверждено", tone: "success" },
  ignored: { label: "отменено", tone: "neutral" },
  duplicate: { label: "дубликат", tone: "danger" },
};

export function toManualOperationRowModel(
  operation: ManualOperationDto,
): ManualOperationRowModel {
  const operationView = operation.money
    ? operationPresentation[operation.money.operationType]
    : operationPresentation.adjustment;
  const statusView = statusPresentation[operation.status];
  return {
    id: operation.id,
    anchorId: `operation-${operation.id}`,
    canCancel: operation.capabilities.canCancel,
    canDelete: operation.capabilities.canDelete,
    canEdit: operation.capabilities.canEdit,
    canRestore: operation.capabilities.canRestore,
    date: operation.operationDate,
    description: operation.description || "Без описания",
    money: operation.money
      ? {
          amount: formatMoneyAmount(
            operation.money.amount,
            operation.money.operationType,
          ),
          currency: operation.money.currency,
          tone: operation.money.operationType,
        }
      : null,
    meta: operationMeta(operation),
    operationLabel: operationView.label,
    operationTone: operationView.tone,
    statusLabel: statusView.label,
    statusTone: statusView.tone,
    version: operation.version,
  };
}

export function manualOperationsTotalLabel(total: number): string {
  const remainder100 = total % 100;
  const remainder10 = total % 10;
  if (remainder10 === 1 && remainder100 !== 11) {
    return `${total} ручная операция`;
  }
  if ([2, 3, 4].includes(remainder10) && ![12, 13, 14].includes(remainder100)) {
    return `${total} ручные операции`;
  }
  return `${total} ручных операций`;
}

function operationMeta(operation: ManualOperationDto): string[] {
  if (operation.money?.operationType === "transfer") {
    return [
      `${operation.sourceAccount?.name ?? "Счёт не найден"} → ${operation.destinationAccount?.name ?? "Счёт не найден"}`,
      "не влияет на прибыль",
    ];
  }

  return [
    operation.category?.name ?? "без категории",
    operation.property?.name,
    operation.account?.name,
  ].filter((value): value is string => Boolean(value));
}
