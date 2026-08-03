import { formatMoneyAmount } from "../../shared/money/format-money";
import type { MoneyTone } from "../../ui/money-value/money-value";
import {
  StatusLabel,
  type StatusTone,
} from "../../ui/status-label/status-label";
import { Tag, type TagTone } from "../../ui/tag/tag";
import type { ImportReviewDto } from "./api/import-review-api";
import styles from "./review-item-presentation.module.css";

export type ReviewItemDto = ImportReviewDto["items"][number];
export type RowProblem = NonNullable<
  ImportReviewDto["validation"]
>["rowProblems"][number];
export type LifecycleAction =
  ReviewItemDto["lifecycle"]["allowedActions"][number];

type ReviewOutcomePresentation = {
  detail: string[];
  label: string;
  result: string;
  resultKind: "meaning" | "route";
  state: "confirmed" | "pending" | "incomplete";
  tone: NonNullable<ReviewItemDto["classification"]["operationType"]>;
};

export function ReviewOutcome({
  outcome,
}: {
  outcome: ReviewOutcomePresentation;
}) {
  return (
    <section
      aria-label="Итог операции"
      className={styles.reviewOutcome}
      data-result-kind={outcome.resultKind}
      data-state={outcome.state}
      data-tone={outcome.tone}
    >
      <span className={styles.outcomeLabel}>{outcome.label}</span>
      <strong className={styles.outcomeResult}>{outcome.result}</strong>
      {outcome.detail.map((detail) => (
        <span className={styles.outcomeDetail} key={detail}>
          {detail}
        </span>
      ))}
    </section>
  );
}

export function reviewOutcomePresentation({
  categories,
  item,
  properties,
}: {
  categories: ImportReviewDto["references"]["categories"];
  item: ReviewItemDto;
  properties: ImportReviewDto["references"]["properties"];
}): ReviewOutcomePresentation | null {
  const operationType = item.classification.operationType;
  if (
    operationType === null ||
    (item.isTerminal && item.status !== "confirmed")
  ) {
    return null;
  }

  const state =
    item.status === "confirmed"
      ? "confirmed"
      : item.confirmability.canConfirm
        ? "pending"
        : "incomplete";
  const label = {
    incomplete: "Предварительный результат",
    pending: "Готово к проведению",
    confirmed: "Проведено",
  }[state];

  if (operationType === "transfer") {
    return {
      detail: [],
      label,
      result: transferOutcomeRoute(item),
      resultKind: "route",
      state,
      tone: operationType,
    };
  }

  const category = categories.find(
    (candidate) => candidate.id === item.selection.categoryId,
  );
  const property = properties.find(
    (candidate) => candidate.id === item.selection.propertyId,
  );
  const operation = operationPresentation(operationType).label;
  const detail: string[] = [];
  if (property) detail.push(`Объект: ${property.name}`);
  return {
    detail,
    label,
    result:
      operationType === "income" || operationType === "expense"
        ? `${operation} → ${category?.name ?? "категория не выбрана"}`
        : operation,
    resultKind: "meaning",
    state,
    tone: operationType,
  };
}

export function ReviewItemMeta({
  categories,
  item,
  properties,
}: {
  categories: ImportReviewDto["references"]["categories"];
  item: ReviewItemDto;
  properties: ImportReviewDto["references"]["properties"];
}) {
  const type = operationPresentation(item.classification.operationType);
  const category = categories.find(
    (candidate) => candidate.id === item.selection.categoryId,
  );
  const property = properties.find(
    (candidate) => candidate.id === item.selection.propertyId,
  );
  const suggestedCategory = categories.find(
    (candidate) => candidate.id === item.ruleSuggestion.categoryId,
  );
  const decisionSource = decisionSourcePresentation(item, suggestedCategory);
  return (
    <div className={styles.meaningSummary}>
      <div className={styles.meaningBadges}>
        <Tag tone={type.tone}>{type.label}</Tag>
        {item.classification.operationType !== "transfer" ? (
          <Tag tone="category" variant="soft">
            {category?.name ?? "Без категории"}
          </Tag>
        ) : null}
        <StatusLabel
          showIcon={statusTone(item.status) !== "neutral"}
          tone={statusTone(item.status)}
          variant={statusNeedsAttention(item.status) ? "soft" : "plain"}
        >
          {statusLabel(item.status)}
        </StatusLabel>
      </div>
      {property ? (
        <span className={styles.propertyFact}>Объект · {property.name}</span>
      ) : null}
      {decisionSource ? (
        <div className={styles.decisionSource}>
          <span>{decisionSource.label}</span>
          {decisionSource.detail ? (
            <strong>{decisionSource.detail}</strong>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function rowReviewActionLabel(item: ReviewItemDto): string {
  if (item.ruleSuggestion.isActive) return "Проверить предложение";
  if (item.classification.operationType === "transfer") {
    return "Проверить перевод";
  }
  if (item.selection.categoryId === null) return "Выбрать категорию";
  return "Проверить операцию";
}

export function ReviewBlockingReason({ reason }: { reason: string }) {
  return (
    <div aria-label="Что мешает подтверждению" className={styles.reviewBlocker}>
      <span>Что мешает подтверждению</span>
      <strong>{reason}</strong>
    </div>
  );
}

export function reviewBlockingReason(item: ReviewItemDto): string | null {
  if (item.isTerminal || item.confirmability.canConfirm) return null;
  const reason = item.confirmability.blockingReasonCodes[0];
  if (!reason) return null;
  return {
    terminal_state: "Строка уже завершена",
    failed_state: "Исправьте ошибку строки",
    duplicate_review_required: "Проверьте возможный дубль",
    normalization_error: "Проверьте распознанные данные",
    missing_operation_date: "Не определена дата операции",
    missing_amount: "Не определена сумма",
    missing_currency: "Не определена валюта",
    missing_source_account: "Не определён исходный счёт",
    missing_operation_type: "Выберите тип операции",
    operation_type_amount_mismatch: "Проверьте тип операции",
    missing_category: "Выберите категорию",
    uncategorized_category: "Выберите конкретную категорию",
    transfer_accounts_required: "Выберите второй счёт перевода",
    same_transfer_account: "Счета перевода должны отличаться",
    unsupported_operation_type: "Этот тип нельзя провести из импорта",
  }[reason];
}

export function RowProblemSignal({
  currency,
  problem,
}: {
  currency: string;
  problem: RowProblem;
}) {
  return (
    <div className={styles.rowProblem}>
      <strong>Нарушена цепочка остатков</strong>
      <span>
        После строки {problem.previousRowIndex} ожидался остаток{" "}
        {formatMoneyAmount(problem.expectedBalanceAfter, null)} {currency},
        получен {formatMoneyAmount(problem.actualBalanceAfter, null)} {currency}
        .
      </span>
    </div>
  );
}

export function operationPresentation(
  operationType: ReviewItemDto["classification"]["operationType"],
): {
  label: string;
  tone: TagTone;
} {
  if (operationType === null)
    return { label: "Тип не определён", tone: "neutral" };
  const presentation = {
    income: { label: "Доход", tone: "income" },
    expense: { label: "Расход", tone: "expense" },
    transfer: { label: "Перевод", tone: "transfer" },
    adjustment: { label: "Корректировка", tone: "adjustment" },
  } satisfies Record<
    NonNullable<ReviewItemDto["classification"]["operationType"]>,
    { label: string; tone: TagTone }
  >;
  return presentation[operationType];
}

export function moneyTone(
  operationType: ReviewItemDto["classification"]["operationType"],
): MoneyTone {
  return operationType ?? "neutral";
}

export function rowWorkflowState(
  item: ReviewItemDto,
  problems: RowProblem[],
): "default" | "problem" | "review" | "settled" | "suggestion" {
  if (problems.length > 0 || item.status === "failed") return "problem";
  if (item.status === "confirmed") return "settled";
  if (item.ruleSuggestion.isActive || item.status === "suggested") {
    return "suggestion";
  }
  if (
    item.isReviewable ||
    item.status === "needs_review" ||
    item.status === "possible_duplicate"
  ) {
    return "review";
  }
  return "default";
}

export function primaryLifecycleActions(
  item: ReviewItemDto,
): LifecycleAction[] {
  return item.status === "possible_duplicate" &&
    item.lifecycle.allowedActions.includes("mark_unique")
    ? ["mark_unique"]
    : [];
}

export function dangerLifecycleActions(item: ReviewItemDto): LifecycleAction[] {
  return item.lifecycle.allowedActions.filter(
    (action) =>
      action === "ignore" ||
      (action === "mark_duplicate" && item.status !== "possible_duplicate"),
  );
}

export function secondaryLifecycleActions(
  item: ReviewItemDto,
): LifecycleAction[] {
  return item.status === "possible_duplicate" &&
    item.lifecycle.allowedActions.includes("mark_duplicate")
    ? ["mark_duplicate"]
    : [];
}

export function overflowLifecycleActions(
  item: ReviewItemDto,
): LifecycleAction[] {
  const primary = new Set(primaryLifecycleActions(item));
  const secondary = new Set(secondaryLifecycleActions(item));
  const danger = new Set(dangerLifecycleActions(item));
  return item.lifecycle.allowedActions.filter(
    (action) =>
      !primary.has(action) && !secondary.has(action) && !danger.has(action),
  );
}

function transferOutcomeRoute(item: ReviewItemDto): string {
  const source =
    item.transfer.sourceAccount?.name ??
    item.sourceAccount?.name ??
    "Исходный счёт не определён";
  const counterparty =
    item.transfer.counterpartyAccount?.name ??
    (item.transfer.direction === "counterparty_to_source"
      ? "Не выбран счёт отправителя"
      : "Не выбран счёт назначения");
  if (item.transfer.direction === "source_to_counterparty") {
    return `${source} → ${counterparty}`;
  }
  if (item.transfer.direction === "counterparty_to_source") {
    return `${counterparty} → ${source}`;
  }
  return "Направление перевода не определено";
}

function decisionSourcePresentation(
  item: ReviewItemDto,
  suggestedCategory:
    ImportReviewDto["references"]["categories"][number] | undefined,
): { detail: string | null; label: string } | null {
  if (item.ruleSuggestion.isActive) {
    const source = item.ruleSuggestion.pattern ?? item.ruleSuggestion.ruleName;
    const target =
      suggestedCategory?.name ??
      (item.ruleSuggestion.operationType
        ? operationPresentation(item.ruleSuggestion.operationType).label
        : null);
    return {
      label: "Предложено правилом",
      detail: source && target ? `${source} → ${target}` : (source ?? target),
    };
  }

  return {
    explicit: { detail: null, label: "Выбрано пользователем" },
    suggested: { detail: null, label: "Предложено системой" },
    inferred: { detail: null, label: "Тип определён по сумме" },
    unknown: null,
  }[item.classification.source];
}

function statusTone(status: ReviewItemDto["status"]): StatusTone {
  if (status === "failed" || status === "duplicate") return "danger";
  if (status === "needs_review" || status === "possible_duplicate")
    return "warning";
  if (status === "confirmed") return "success";
  return "neutral";
}

function statusNeedsAttention(status: ReviewItemDto["status"]): boolean {
  return (
    status === "failed" ||
    status === "duplicate" ||
    status === "needs_review" ||
    status === "possible_duplicate"
  );
}

function statusLabel(status: ReviewItemDto["status"]): string {
  return {
    extracted: "Требует решения",
    normalized: "Требует решения",
    suggested: "Есть предложение",
    needs_review: "Нужна проверка",
    matched: "Проверено как уникальное",
    ignored: "Исключено",
    duplicate: "Дубль",
    possible_duplicate: "Возможный дубль",
    failed: "Ошибка",
    confirmed: "Проведено",
  }[status];
}
