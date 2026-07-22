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
  const [actionsOpen, setActionsOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);
  const reviewButtonRef = useRef<HTMLButtonElement>(null);
  const sourceButtonRef = useRef<HTMLButtonElement>(null);
  const panelId = `review-panel-${item.id}`;
  const sourcePanelId = `source-panel-${item.id}`;
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
  const outcome = reviewOutcomePresentation({
    amount,
    categories,
    currency,
    item,
    properties,
  });

  function closePanel() {
    setPanelOpen(false);
    queueMicrotask(() => reviewButtonRef.current?.focus());
  }

  function toggleReviewPanel() {
    setActionsOpen(false);
    setSourceOpen(false);
    setPanelOpen((open) => !open);
  }

  function toggleSourcePanel() {
    setActionsOpen(false);
    setPanelOpen(false);
    setSourceOpen((open) => !open);
  }

  function closeSourcePanel() {
    setSourceOpen(false);
    queueMicrotask(() => sourceButtonRef.current?.focus());
  }

  const actionStack = (
    <ActionStack
      danger={
        !readonly && (dangerLifecycle.length || item.posting.canUndo) ? (
          <>
            <LifecycleActions
              actions={dangerLifecycle}
              csrfToken={csrfToken}
              documentId={documentId}
              item={item}
              onMenuDismiss={() => setActionsOpen(false)}
              onReviewReconciled={onReviewReconciled}
              readonly={readonly}
            />
            <UndoPostingAction
              csrfToken={csrfToken}
              documentId={documentId}
              item={item}
              onMenuDismiss={() => setActionsOpen(false)}
              onReviewReconciled={onReviewReconciled}
              readonly={readonly}
            />
          </>
        ) : undefined
      }
      disclosureOpen={actionsOpen}
      onDisclosureChange={setActionsOpen}
      overflow={
        <>
          {!readonly && overflowLifecycle.length ? (
            <LifecycleActions
              actions={overflowLifecycle}
              csrfToken={csrfToken}
              documentId={documentId}
              item={item}
              onMenuDismiss={() => setActionsOpen(false)}
              onReviewReconciled={onReviewReconciled}
              readonly={readonly}
            />
          ) : null}
          <Button
            aria-controls={sourcePanelId}
            aria-expanded={sourceOpen}
            onClick={toggleSourcePanel}
            ref={sourceButtonRef}
          >
            Исходные данные
          </Button>
        </>
      }
      primary={
        readonly ? undefined : primaryLifecycle.length ? (
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
            onClick={toggleReviewPanel}
            ref={reviewButtonRef}
            tone="primary"
          >
            {reviewActionLabel}
          </Button>
        ) : undefined
      }
      secondary={
        !readonly &&
        (primaryLifecycle.length || canQuickConfirmSuggestion) &&
        hasReviewPanel ? (
          <Button
            aria-controls={panelId}
            aria-expanded={panelOpen}
            onClick={toggleReviewPanel}
            ref={reviewButtonRef}
            tone="secondary"
          >
            Изменить
          </Button>
        ) : undefined
      }
    />
  );
  const aside =
    outcome || actionStack ? (
      <div className={styles.outcomeRail}>
        {outcome ? <ReviewOutcome outcome={outcome} /> : null}
        {actionStack}
      </div>
    ) : undefined;

  return (
    <WorkbenchRow
      aside={aside}
      {...(item.normalized.operationDate
        ? { date: item.normalized.operationDate }
        : {})}
      description={description}
      expansion={
        <>
          {hasReviewPanel ? (
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
                onCancel={closePanel}
                onCategoryCreated={onCategoryCreated}
                onReviewReconciled={onReviewReconciled}
                properties={properties}
                readonly={readonly}
              />
            </ExpansionPanel>
          ) : null}
          <ExpansionPanel
            id={sourcePanelId}
            isOpen={sourceOpen}
            onClose={closeSourcePanel}
            title={`Исходные данные строки ${item.rowIndex}`}
          >
            <SourceSummary currency={currency} item={item} />
          </ExpansionPanel>
        </>
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
      state={
        (hasReviewPanel && panelOpen) || sourceOpen ? "working" : "default"
      }
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
      workflowState={rowWorkflowState(item, problems)}
    />
  );
}

type ReviewOutcomePresentation = {
  detail: string[];
  label: string;
  result: string;
  resultKind: "money" | "route";
  state: "confirmed" | "pending" | "incomplete";
  tone: NonNullable<ReviewItemDto["classification"]["operationType"]>;
};

function ReviewOutcome({ outcome }: { outcome: ReviewOutcomePresentation }) {
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

function reviewOutcomePresentation({
  amount,
  categories,
  currency,
  item,
  properties,
}: {
  amount: string | null;
  categories: ReviewItemProps["categories"];
  currency: string;
  item: ReviewItemDto;
  properties: ReviewItemProps["properties"];
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
  const label = outcomeLabel(operationType, state === "confirmed");
  const formattedAmount =
    amount === null
      ? "Сумма не распознана"
      : `${formatOutcomeAmount(amount)}${currency ? ` ${currency}` : ""}`;

  if (operationType === "transfer") {
    return {
      detail: [formattedAmount],
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
  const detail = [
    category ? `Категория: ${category.name}` : "Категория не выбрана",
  ];
  if (property) detail.push(`Объект: ${property.name}`);
  return {
    detail,
    label,
    result: formattedAmount,
    resultKind: "money",
    state,
    tone: operationType,
  };
}

function outcomeLabel(
  operationType: NonNullable<ReviewItemDto["classification"]["operationType"]>,
  confirmed: boolean,
): string {
  if (operationType === "adjustment") {
    return confirmed ? "Создана корректировка" : "Будет создана корректировка";
  }
  const noun = {
    income: "доход",
    expense: "расход",
    transfer: "перевод",
  }[operationType];
  return confirmed ? `Создан ${noun}` : `Будет создан ${noun}`;
}

function transferOutcomeRoute(item: ReviewItemDto): string {
  const source = item.sourceAccount?.name ?? "Исходный счёт не определён";
  const counterparty =
    item.status === "confirmed"
      ? "Счёт перевода"
      : item.transfer.direction === "counterparty_to_source"
        ? "Не выбран счёт отправителя"
        : "Не выбран счёт назначения";
  if (item.transfer.direction === "source_to_counterparty") {
    return `${source} → ${counterparty}`;
  }
  if (item.transfer.direction === "counterparty_to_source") {
    return `${counterparty} → ${source}`;
  }
  return "Направление перевода не определено";
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

function SourceSummary({
  currency,
  item,
}: {
  currency: string;
  item: ReviewItemDto;
}) {
  const normalizedChanged = hasNormalizedChanges(item);
  return (
    <>
      <div className={styles.sourceSummary}>
        <span>Строка {item.rowIndex}</span>
        {item.normalized.balanceAfter ? (
          <span>
            Остаток после строки:{" "}
            {formatPlainMoney(item.normalized.balanceAfter)} {currency}
          </span>
        ) : null}
        <span>
          {normalizedChanged ? "Данные нормализованы" : "Без нормализации"}
        </span>
      </div>
      <SourceComparison item={item} compact />
    </>
  );
}

function rowReviewActionLabel(item: ReviewItemDto): string {
  if (item.ruleSuggestion.isActive) return "Проверить предложение";
  if (
    item.classification.operationType === "transfer" ||
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

function formatOutcomeAmount(value: string): string {
  return formatReviewAmount(value, null).replace(/^[+−-]/, "");
}

function rowWorkflowState(
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
