import type { components } from "../../../api/generated/schema";
import { formatMoneyAmount } from "../../../shared/money/format-money";
import type { MoneyTone } from "../../../ui/money-value/money-value";
import type { StatusTone } from "../../../ui/status-label/status-label";
import type { TagTone } from "../../../ui/tag/tag";

type ManualOperationDto = components["schemas"]["ManualOperationApiResponse"];
type OperationDto = components["schemas"]["OperationApiResponse"];
type LedgerOperationDto = ManualOperationDto | OperationDto;
type OperationType = components["schemas"]["OperationType"];
type OperationStatus = components["schemas"]["OperationStatus"];

export type ManualOperationRowModel = {
  id: string;
  anchorId: string;
  accountId: string | null;
  canCancel: boolean;
  canDelete: boolean;
  canEdit: boolean;
  canRestore: boolean;
  accountLabel: string | null;
  categoryLabel: string | null;
  date: string;
  description: string;
  editKind: "manual" | "imported" | "none";
  money: { amount: string; currency: string; tone: MoneyTone } | null;
  operationLabel: string;
  operationTone: TagTone;
  propertyLabel: string | null;
  category: { id: string; name: string } | null;
  property: { id: string; name: string } | null;
  readonlyReasonLabel: string | null;
  source: OperationDto["source"] | null;
  sourceTarget: { label: string; url: string } | null;
  status: OperationStatus;
  statusLabel: string;
  statusTone: StatusTone;
  sourceLabel: string | null;
  transferRouteLabel: string | null;
  version: number;
};

const operationPresentation: Record<
  OperationType,
  { label: string; tone: TagTone }
> = {
  income: { label: "Доход", tone: "income" },
  expense: { label: "Расход", tone: "expense" },
  transfer: { label: "Перевод", tone: "transfer" },
  adjustment: { label: "Корректировка", tone: "adjustment" },
};

const statusPresentation: Record<
  OperationStatus,
  { label: string; tone: StatusTone }
> = {
  draft: { label: "Черновик", tone: "warning" },
  needs_review: { label: "Нужна проверка", tone: "warning" },
  confirmed: { label: "Подтверждено", tone: "success" },
  ignored: { label: "Отменено", tone: "neutral" },
  duplicate: { label: "Дубликат", tone: "danger" },
};

export function toManualOperationRowModel(
  operation: LedgerOperationDto,
): ManualOperationRowModel {
  const operationView = operationPresentation[operation.operationType];
  const statusView = statusPresentation[operation.status];
  const source = "source" in operation ? operation.source : null;
  const manualActions = source === null || source === "manual";
  const editKind =
    "editKind" in operation.capabilities
      ? operation.capabilities.editKind
      : operation.capabilities.canEdit
        ? "manual"
        : "none";
  return {
    id: operation.id,
    anchorId: `operation-${operation.id}`,
    accountId: operation.account?.id ?? null,
    canCancel: manualActions && operation.capabilities.canCancel,
    canDelete: manualActions && operation.capabilities.canDelete,
    canEdit: operation.capabilities.canEdit,
    canRestore: manualActions && operation.capabilities.canRestore,
    accountLabel: operation.account?.name ?? null,
    categoryLabel: operation.category?.name ?? null,
    date: operation.operationDate,
    description: operation.description || "Без описания",
    editKind,
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
    category: operation.category,
    property: operation.property,
    readonlyReasonLabel:
      "source" in operation && operation.capabilities.readonlyReason
        ? readonlyReasonPresentation[operation.capabilities.readonlyReason]
        : null,
    source,
    sourceTarget:
      "provenance" in operation ? operationSourceTarget(operation) : null,
    status: operation.status,
    statusLabel: statusView.label,
    statusTone: statusView.tone,
    sourceLabel: source ? sourcePresentation[source] : null,
    transferRouteLabel:
      operation.operationType === "transfer"
        ? `${operation.sourceAccount?.name ?? "Счёт не найден"} → ${operation.destinationAccount?.name ?? "Счёт не найден"}`
        : null,
    version: operation.version,
  };
}

const sourcePresentation: Record<OperationDto["source"], string> = {
  manual: "Вручную",
  bank_pdf: "Импорт",
  debt: "Долг",
  system: "Система",
};

const readonlyReasonPresentation: Record<
  NonNullable<OperationDto["capabilities"]["readonlyReason"]>,
  string
> = {
  financial_write_forbidden: "Недостаточно прав для изменения операции.",
  operation_state_readonly: "Операцию в этом состоянии нельзя изменить.",
  source_workflow_required: "Изменения выполняются в исходном разделе.",
  system_operation: "Системная операция доступна только для просмотра.",
};

function operationSourceTarget(
  operation: OperationDto,
): { label: string; url: string } | null {
  const provenance = operation.provenance;
  if (provenance?.kind === "import") {
    if (provenance.uploadedDocumentId && provenance.rawTransactionId) {
      return {
        label: "Открыть импорт",
        url: `/imports/documents/${provenance.uploadedDocumentId}/review#raw-${provenance.rawTransactionId}`,
      };
    }
    if (provenance.uploadedDocumentId) {
      return {
        label: "Открыть документ",
        url: `/imports/documents/${provenance.uploadedDocumentId}`,
      };
    }
    return { label: "Найти импорт", url: "/imports" };
  }
  if (provenance?.kind === "debt") {
    return {
      label: "Открыть долг",
      url: provenance.debtAccountId
        ? `/debts/${provenance.debtAccountId}`
        : "/debts",
    };
  }
  return null;
}

export function operationsTotalLabel(total: number): string {
  const remainder100 = total % 100;
  const remainder10 = total % 10;
  if (remainder10 === 1 && remainder100 !== 11) return `${total} операция`;
  if ([2, 3, 4].includes(remainder10) && ![12, 13, 14].includes(remainder100)) {
    return `${total} операции`;
  }
  return `${total} операций`;
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
