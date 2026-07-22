import { useRef, useState } from "react";

import { formatIsoDate } from "../../shared/date/format-date";
import { ActionStack } from "../../ui/action-stack/action-stack";
import { Badge, type BadgeTone } from "../../ui/badge/badge";
import { Button } from "../../ui/button/button";
import { ExpansionPanel } from "../../ui/expansion-panel/expansion-panel";
import { MoneyValue, type MoneyTone } from "../../ui/money-value/money-value";
import { WorkbenchRow } from "../../ui/workbench-row/workbench-row";
import type { ImportReviewDto } from "./api/import-review-api";
import type { ImportReviewCategoryReferenceDto } from "./api/import-review-mutations";
import { ClassificationPanel } from "./classification-panel";
import styles from "./import-review.module.css";
import { LifecycleActions } from "./lifecycle-actions";
import { ConfirmPostingAction, UndoPostingAction } from "./posting-actions";

type ReviewItemDto = ImportReviewDto["items"][number];
type RowProblem = NonNullable<
  ImportReviewDto["validation"]
>["rowProblems"][number];
type LifecycleAction = ReviewItemDto["lifecycle"]["allowedActions"][number];

type ReviewItemProps = {
  categories: ImportReviewDto["references"]["categories"];
  csrfToken: string;
  documentId: string;
  item: ReviewItemDto;
  onCategoryCreated: (category: ImportReviewCategoryReferenceDto) => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  problems: RowProblem[];
  properties: ImportReviewDto["references"]["properties"];
  readonly: boolean;
};

export function ReviewItem({
  categories,
  csrfToken,
  documentId,
  item,
  onCategoryCreated,
  onReviewReconciled,
  problems,
  properties,
  readonly,
}: ReviewItemProps) {
  const [panelOpen, setPanelOpen] = useState(false);
  const reviewButtonRef = useRef<HTMLButtonElement>(null);
  const panelId = `review-panel-${item.id}`;
  const operationType = item.classification.operationType;
  const amount = item.normalized.amount ?? item.raw.amount;
  const currency = item.normalized.currency ?? item.raw.currency ?? "";
  const description =
    item.normalized.description ?? item.raw.description ?? "Без описания";
  const primaryLifecycle = primaryLifecycleActions(item);
  const overflowLifecycle = overflowLifecycleActions(item);
  const dangerLifecycle = dangerLifecycleActions(item);
  const hasReviewPanel = !item.isTerminal;
  const canQuickConfirmSuggestion =
    item.ruleSuggestion.wasAutoApplied && item.confirmability.canConfirm;
  const reviewActionLabel = rowReviewActionLabel(item);

  function closePanel() {
    setPanelOpen(false);
    queueMicrotask(() => reviewButtonRef.current?.focus());
  }

  const aside = readonly ? undefined : primaryLifecycle.length ||
    overflowLifecycle.length ||
    dangerLifecycle.length ||
    hasReviewPanel ||
    item.posting.canUndo ? (
    <ActionStack
      danger={
        dangerLifecycle.length || item.posting.canUndo ? (
          <>
            <LifecycleActions
              actions={dangerLifecycle}
              csrfToken={csrfToken}
              documentId={documentId}
              item={item}
              onReviewReconciled={onReviewReconciled}
              readonly={readonly}
            />
            <UndoPostingAction
              csrfToken={csrfToken}
              documentId={documentId}
              item={item}
              onReviewReconciled={onReviewReconciled}
              readonly={readonly}
            />
          </>
        ) : undefined
      }
      overflow={
        overflowLifecycle.length ? (
          <LifecycleActions
            actions={overflowLifecycle}
            csrfToken={csrfToken}
            documentId={documentId}
            item={item}
            onReviewReconciled={onReviewReconciled}
            readonly={readonly}
          />
        ) : undefined
      }
      primary={
        primaryLifecycle.length ? (
          <LifecycleActions
            actions={primaryLifecycle}
            csrfToken={csrfToken}
            documentId={documentId}
            item={item}
            onReviewReconciled={onReviewReconciled}
            readonly={readonly}
          />
        ) : canQuickConfirmSuggestion ? (
          <ConfirmPostingAction
            csrfToken={csrfToken}
            dirty={false}
            documentId={documentId}
            evaluation={{
              itemId: item.id,
              classification: item.classification,
              selection: item.selection,
              confirmability: item.confirmability,
              ruleSuggestion: item.ruleSuggestion,
            }}
            item={item}
            onReviewReconciled={onReviewReconciled}
            variant="quick"
          />
        ) : hasReviewPanel ? (
          <Button
            aria-controls={panelId}
            aria-expanded={panelOpen}
            onClick={() => setPanelOpen((open) => !open)}
            ref={reviewButtonRef}
            tone="primary"
          >
            {reviewActionLabel}
          </Button>
        ) : undefined
      }
      secondary={
        (primaryLifecycle.length || canQuickConfirmSuggestion) &&
        hasReviewPanel ? (
          <Button
            aria-controls={panelId}
            aria-expanded={panelOpen}
            onClick={() => setPanelOpen((open) => !open)}
            ref={reviewButtonRef}
            tone="secondary"
          >
            Изменить
          </Button>
        ) : undefined
      }
    />
  ) : undefined;

  return (
    <WorkbenchRow
      aside={aside}
      {...(item.normalized.operationDate
        ? { date: item.normalized.operationDate }
        : {})}
      description={description}
      expansion={
        hasReviewPanel ? (
          <ExpansionPanel
            id={panelId}
            isOpen={panelOpen}
            onClose={closePanel}
            title={`Разобрать строку ${item.rowIndex}`}
          >
            <ClassificationPanel
              categories={categories}
              csrfToken={csrfToken}
              documentId={documentId}
              item={item}
              onCategoryCreated={onCategoryCreated}
              onReviewReconciled={onReviewReconciled}
              properties={properties}
              readonly={readonly}
            />
            <SourceSummary currency={currency} item={item} />
          </ExpansionPanel>
        ) : undefined
      }
      financialHierarchy
      id={`raw-${item.id}`}
      details={
        item.raw.accountHint || item.sourceAccount ? (
          <span>
            {item.raw.accountHint ? `По карте ${item.raw.accountHint}` : ""}
            {item.raw.accountHint && item.sourceAccount ? " · " : ""}
            {item.sourceAccount?.name ?? ""}
          </span>
        ) : undefined
      }
      meta={
        <ReviewItemMeta
          categories={categories}
          item={item}
          properties={properties}
        />
      }
      signals={
        problems.length > 0
          ? problems.map((problem) => (
              <RowProblemSignal
                currency={currency}
                key={`${problem.code}-${problem.itemId}`}
                problem={problem}
              />
            ))
          : undefined
      }
      state={panelOpen ? "working" : "default"}
      tabIndex={-1}
      value={
        amount !== null ? (
          <MoneyValue
            amount={formatReviewAmount(amount, operationType)}
            currency={currency}
            tone={moneyTone(operationType)}
          />
        ) : (
          <span className={styles.missingMoney}>Сумма не распознана</span>
        )
      }
    />
  );
}

function ReviewItemMeta({
  categories,
  item,
  properties,
}: {
  categories: ReviewItemProps["categories"];
  item: ReviewItemDto;
  properties: ReviewItemProps["properties"];
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
        <Badge tone={type.tone}>{type.label}</Badge>
        {item.classification.operationType !== "transfer" ? (
          <Badge tone="category" variant="soft">
            {category?.name ?? "Без категории"}
          </Badge>
        ) : null}
        <Badge tone={statusTone(item.status)} variant="status">
          {statusLabel(item.status)}
        </Badge>
      </div>
      {property ? (
        <span className={styles.propertyFact}>Объект · {property.name}</span>
      ) : null}
      <div className={styles.decisionSource}>
        <span>{decisionSource.label}</span>
        {decisionSource.detail ? (
          <strong>{decisionSource.detail}</strong>
        ) : null}
      </div>
    </div>
  );
}

function decisionSourcePresentation(
  item: ReviewItemDto,
  suggestedCategory:
    ImportReviewDto["references"]["categories"][number] | undefined,
): { detail: string | null; label: string } {
  if (item.ruleSuggestion.isActive) {
    const ruleIdentity = item.ruleSuggestion.ruleName
      ? ` «${item.ruleSuggestion.ruleName}»`
      : "";
    const source = item.ruleSuggestion.pattern ?? item.ruleSuggestion.ruleName;
    const target =
      suggestedCategory?.name ??
      (item.ruleSuggestion.operationType
        ? operationPresentation(item.ruleSuggestion.operationType).label
        : null);
    return {
      label: `Предложено правилом${ruleIdentity}`,
      detail: source && target ? `${source} → ${target}` : (source ?? target),
    };
  }

  return {
    explicit: { detail: null, label: "Выбрано пользователем" },
    suggested: { detail: null, label: "Предложено системой" },
    inferred: { detail: null, label: "Тип определён по сумме" },
    unknown: { detail: null, label: "Источник решения не определён" },
  }[item.classification.source];
}

function SourceSummary({
  currency,
  item,
}: {
  currency: string;
  item: ReviewItemDto;
}) {
  const normalizedChanged = hasNormalizedChanges(item);
  return (
    <div className={styles.sourceSummary}>
      <span>Строка {item.rowIndex}</span>
      {item.normalized.balanceAfter ? (
        <span>
          Остаток после строки: {formatPlainMoney(item.normalized.balanceAfter)}{" "}
          {currency}
        </span>
      ) : null}
      <details className={styles.sourceDetails}>
        <summary>
          Сверить с исходной строкой
          {normalizedChanged ? " · данные нормализованы" : ""}
        </summary>
        <SourceComparison item={item} compact />
      </details>
    </div>
  );
}

function rowReviewActionLabel(item: ReviewItemDto): string {
  if (item.ruleSuggestion.isActive) return "Проверить предложение";
  if (
    item.transfer.rawRowCandidates.length > 0 ||
    item.transfer.existingOperationCandidates.length > 0
  ) {
    return "Проверить перевод";
  }
  if (item.selection.categoryId === null) return "Выбрать категорию";
  return "Проверить и провести";
}

function RowProblemSignal({
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
        {formatPlainMoney(problem.expectedBalanceAfter)} {currency}, получен{" "}
        {formatPlainMoney(problem.actualBalanceAfter)} {currency}.
      </span>
    </div>
  );
}

function SourceComparison({
  compact = false,
  item,
}: {
  compact?: boolean;
  item: ReviewItemDto;
}) {
  return (
    <section
      className={
        compact ? styles.sourceComparisonCompact : styles.sourceComparison
      }
    >
      {!compact ? (
        <header>
          <div>
            <p className={styles.sectionEyebrow}>Проверка парсера</p>
            <h4>Исходные и нормализованные данные</h4>
          </div>
          {hasNormalizedChanges(item) ? (
            <Badge tone="warning">Есть изменения</Badge>
          ) : (
            <Badge tone="neutral">Без изменений</Badge>
          )}
        </header>
      ) : null}
      <div className={styles.sourceComparisonGrid}>
        <SourceValue
          label="Дата"
          normalized={
            item.normalized.operationDate
              ? formatIsoDate(item.normalized.operationDate)
              : null
          }
          raw={item.raw.operationDate}
        />
        <SourceValue
          label="Описание"
          normalized={item.normalized.description}
          raw={item.raw.description}
        />
        <SourceValue
          label="Сумма"
          normalized={item.normalized.amount}
          raw={item.raw.amount}
        />
        <SourceValue
          label="Валюта"
          normalized={item.normalized.currency}
          raw={item.raw.currency}
        />
        <SourceValue
          label="Остаток"
          normalized={item.normalized.balanceAfter}
          raw={item.raw.balanceAfter}
        />
        <SourceValue
          label="Подсказка счёта"
          normalized={null}
          raw={item.raw.accountHint}
        />
      </div>
    </section>
  );
}

function SourceValue({
  label,
  normalized,
  raw,
}: {
  label: string;
  normalized: string | null;
  raw: string | null;
}) {
  const changed = normalized !== null && raw !== null && normalized !== raw;
  return (
    <div
      className={styles.sourceValue}
      data-changed={changed ? "true" : "false"}
    >
      <strong>{label}</strong>
      <dl>
        <div>
          <dt>В выписке</dt>
          <dd>{raw ?? "—"}</dd>
        </div>
        <div>
          <dt>После парсера</dt>
          <dd>{normalized ?? "—"}</dd>
        </div>
      </dl>
    </div>
  );
}

function hasNormalizedChanges(item: ReviewItemDto): boolean {
  return [
    [item.raw.operationDate, item.normalized.operationDate],
    [item.raw.description, item.normalized.description],
    [item.raw.amount, item.normalized.amount],
    [item.raw.currency, item.normalized.currency],
    [item.raw.balanceAfter, item.normalized.balanceAfter],
  ].some(
    ([raw, normalized]) =>
      raw !== null && normalized !== null && raw !== normalized,
  );
}

function operationPresentation(
  operationType: ReviewItemDto["classification"]["operationType"],
): {
  label: string;
  tone: BadgeTone;
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
    { label: string; tone: BadgeTone }
  >;
  return presentation[operationType];
}

function moneyTone(
  operationType: ReviewItemDto["classification"]["operationType"],
): MoneyTone {
  return operationType ?? "neutral";
}

function formatReviewAmount(
  value: string,
  operationType: ReviewItemDto["classification"]["operationType"],
): string {
  const normalized = value.replace(",", ".");
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(normalized);
  if (!match) return value;
  const integer = (match[2] ?? "0").replace(/\B(?=(\d{3})+(?!\d))/g, " ");
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

function formatPlainMoney(value: string): string {
  return formatReviewAmount(value, null);
}

function primaryLifecycleActions(item: ReviewItemDto): LifecycleAction[] {
  return item.status === "possible_duplicate" &&
    item.lifecycle.allowedActions.includes("mark_unique")
    ? ["mark_unique"]
    : [];
}

function dangerLifecycleActions(item: ReviewItemDto): LifecycleAction[] {
  return item.lifecycle.allowedActions.filter(
    (action) => action === "mark_duplicate" || action === "ignore",
  );
}

function overflowLifecycleActions(item: ReviewItemDto): LifecycleAction[] {
  const primary = new Set(primaryLifecycleActions(item));
  const danger = new Set(dangerLifecycleActions(item));
  return item.lifecycle.allowedActions.filter(
    (action) => !primary.has(action) && !danger.has(action),
  );
}

function statusTone(status: ReviewItemDto["status"]): BadgeTone {
  if (status === "failed" || status === "duplicate") return "danger";
  if (status === "needs_review" || status === "possible_duplicate")
    return "warning";
  if (status === "confirmed") return "success";
  return "neutral";
}

function statusLabel(status: ReviewItemDto["status"]): string {
  return {
    extracted: "Извлечено",
    normalized: "Нормализовано",
    suggested: "Есть предложение",
    needs_review: "Нужна проверка",
    matched: "Проверено как уникальное",
    ignored: "Игнорируется",
    duplicate: "Дубль",
    possible_duplicate: "Возможный дубль",
    failed: "Ошибка",
    confirmed: "Проведено",
  }[status];
}
