import type { components } from "../../../api/generated/schema";
import { formatMoneyAmount } from "../../../shared/money/format-money";
import type { BadgeTone } from "../../../ui/badge/badge";
import type { MoneyTone } from "../../../ui/money-value/money-value";

type ManualOperationDto = components["schemas"]["ManualOperationApiResponse"];
type OperationType = components["schemas"]["OperationType"];
type OperationStatus = components["schemas"]["OperationStatus"];

export type ManualOperationRowModel = {
  id: string;
  anchorId: string;
  canCancel: boolean;
  canDelete: boolean;
  canEdit: boolean;
  canRestore: boolean;
  accountLabel: string | null;
  categoryLabel: string | null;
  date: string;
  description: string;
  money: { amount: string; currency: string; tone: MoneyTone } | null;
  operationLabel: string;
  operationTone: BadgeTone;
  propertyLabel: string | null;
  statusLabel: string;
  statusTone: BadgeTone;
  transferRouteLabel: string | null;
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
  const operationView = operationPresentation[operation.operationType];
  const statusView = statusPresentation[operation.status];
  return {
    id: operation.id,
    anchorId: `operation-${operation.id}`,
    canCancel: operation.capabilities.canCancel,
    canDelete: operation.capabilities.canDelete,
    canEdit: operation.capabilities.canEdit,
    canRestore: operation.capabilities.canRestore,
    accountLabel: operation.account?.name ?? null,
    categoryLabel: operation.category?.name ?? null,
    date: operation.operationDate,
    description: operation.description || "Без описания",
    money: operation.money
      ? {
          amount: formatMoneyAmount(
            operation.money.amount,
            operation.operationType,
          ),
          currency: operation.money.currency,
          tone: operation.operationType,
        }
      : null,
    operationLabel: operationView.label,
    operationTone: operationView.tone,
    propertyLabel: operation.property?.name ?? null,
    statusLabel: statusView.label,
    statusTone: statusView.tone,
    transferRouteLabel:
      operation.operationType === "transfer"
        ? `${operation.sourceAccount?.name ?? "Счёт не найден"} → ${operation.destinationAccount?.name ?? "Счёт не найден"}`
        : null,
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
