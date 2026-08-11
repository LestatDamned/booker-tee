import { useRef, useState } from "react";

import { formatIsoDate } from "../../shared/date/format-date";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { ActionStack } from "../../ui/action-stack/action-stack";
import { Button, RouterButtonLink } from "../../ui/button/button";
import { ExpansionPanel } from "../../ui/expansion-panel/expansion-panel";
import { MoneyValue } from "../../ui/money-value/money-value";
import { WorkbenchRow } from "../../ui/workbench-row/workbench-row";
import type { ImportReviewDto } from "./api/import-review-api";
import type { ImportReviewCategoryReferenceDto } from "./api/import-review-mutations";
import { operationHref } from "../operations/operation-navigation";
import { ClassificationPanel } from "./classification-panel";
import { DuplicateComparison } from "./duplicate-comparison";
import {
  ExistingOperationComparison,
  ExistingOperationLinkAction,
} from "./existing-operation-match";
import styles from "./review-item.module.css";
import { LifecycleActions } from "./lifecycle-actions";
import { ConfirmPostingAction, UndoPostingAction } from "./posting-actions";
import {
  dangerLifecycleActions,
  moneyTone,
  overflowLifecycleActions,
  primaryLifecycleActions,
  ReviewBlockingReason,
  ReviewItemMeta,
  ReviewOutcome,
  reviewBlockingReason,
  reviewOutcomePresentation,
  rowReviewActionLabel,
  RowProblemSignal,
  rowWorkflowState,
  secondaryLifecycleActions,
  type ReviewItemDto,
  type RowProblem,
} from "./review-item-presentation";
import { SourceSummary } from "./source-comparison";

type ReviewItemProps = {
  categories: ImportReviewDto["references"]["categories"];
  csrfToken: string;
  documentId: string;
  documentSourceAccountName: string | null;
  item: ReviewItemDto;
  onCategoryCreated: (category: ImportReviewCategoryReferenceDto) => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  onSuccess: (message: string) => void;
  problems: RowProblem[];
  properties: ImportReviewDto["references"]["properties"];
  readonly: boolean;
};

export function ReviewItem({
  categories,
  csrfToken,
  documentId,
  documentSourceAccountName,
  item,
  onCategoryCreated,
  onReviewReconciled,
  onSuccess,
  problems,
  properties,
  readonly,
}: ReviewItemProps) {
  const [actionsOpen, setActionsOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [selectedOperationId, setSelectedOperationId] = useState(
    item.existingOperationCandidates[0]?.operationId ?? "",
  );
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
  const secondaryLifecycle = secondaryLifecycleActions(item);
  const overflowLifecycle = overflowLifecycleActions(item);
  const dangerLifecycle = dangerLifecycleActions(item);
  const hasReviewPanel = !item.isTerminal;
  const canQuickConfirmSuggestion =
    item.ruleSuggestion.wasAutoApplied && item.confirmability.canConfirm;
  const reviewActionLabel = rowReviewActionLabel(item);
  const outcome = reviewOutcomePresentation({
    categories,
    item,
    properties,
  });
  const blockingReason = reviewBlockingReason(item);
  const existingOperationId = item.existingOperationCandidates.some(
    (candidate) => candidate.operationId === selectedOperationId,
  )
    ? selectedOperationId
    : (item.existingOperationCandidates[0]?.operationId ?? "");

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
              onSuccess={onSuccess}
              readonly={readonly}
            />
            <UndoPostingAction
              csrfToken={csrfToken}
              documentId={documentId}
              item={item}
              onMenuDismiss={() => setActionsOpen(false)}
              onReviewReconciled={onReviewReconciled}
              onSuccess={onSuccess}
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
              onSuccess={onSuccess}
              readonly={readonly}
            />
          ) : null}
          <Button
            aria-controls={sourcePanelId}
            aria-expanded={sourceOpen}
            onClick={toggleSourcePanel}
            ref={sourceButtonRef}
            icon="source"
          >
            Исходные данные
          </Button>
        </>
      }
      primary={
        readonly ? undefined : existingOperationId ? (
          <ExistingOperationLinkAction
            csrfToken={csrfToken}
            documentId={documentId}
            item={item}
            onReviewReconciled={onReviewReconciled}
            onSuccess={onSuccess}
            operationId={existingOperationId}
          />
        ) : primaryLifecycle.length ? (
          <LifecycleActions
            actions={primaryLifecycle}
            csrfToken={csrfToken}
            documentId={documentId}
            item={item}
            onReviewReconciled={onReviewReconciled}
            onSuccess={onSuccess}
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
            onSuccess={onSuccess}
            variant="quick"
          />
        ) : hasReviewPanel ? (
          <Button
            aria-controls={panelId}
            aria-expanded={panelOpen}
            onClick={toggleReviewPanel}
            ref={reviewButtonRef}
            tone="primary"
            icon="edit"
          >
            {reviewActionLabel}
          </Button>
        ) : undefined
      }
      secondary={
        !readonly && existingOperationId && primaryLifecycle.length ? (
          <LifecycleActions
            actions={primaryLifecycle}
            csrfToken={csrfToken}
            documentId={documentId}
            item={item}
            onReviewReconciled={onReviewReconciled}
            onSuccess={onSuccess}
            readonly={readonly}
            toneOverride="secondary"
          />
        ) : !readonly && existingOperationId && hasReviewPanel ? (
          <Button
            aria-controls={panelId}
            aria-expanded={panelOpen}
            onClick={toggleReviewPanel}
            ref={reviewButtonRef}
            tone="secondary"
            icon="edit"
          >
            Это отдельная операция
          </Button>
        ) : !readonly && secondaryLifecycle.length ? (
          <LifecycleActions
            actions={secondaryLifecycle}
            csrfToken={csrfToken}
            documentId={documentId}
            item={item}
            onReviewReconciled={onReviewReconciled}
            onSuccess={onSuccess}
            readonly={readonly}
          />
        ) : !readonly &&
          (primaryLifecycle.length || canQuickConfirmSuggestion) &&
          hasReviewPanel ? (
          <Button
            aria-controls={panelId}
            aria-expanded={panelOpen}
            onClick={toggleReviewPanel}
            ref={reviewButtonRef}
            tone="secondary"
            icon="edit"
          >
            Изменить операцию
          </Button>
        ) : undefined
      }
    />
  );
  const aside =
    outcome || actionStack ? (
      <div className={styles.outcomeRail}>
        {outcome ? <ReviewOutcome outcome={outcome} /> : null}
        {item.posting.operationId ? (
          <RouterButtonLink
            icon="information"
            to={operationHref(item.posting.operationId)}
            tone="secondary"
          >
            Открыть операцию
          </RouterButtonLink>
        ) : null}
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
              title="Операция"
            >
              <ReviewItemContext
                amount={amount}
                currency={currency}
                description={description}
                item={item}
              />
              <ClassificationPanel
                categories={categories}
                csrfToken={csrfToken}
                documentId={documentId}
                item={item}
                onCancel={closePanel}
                onCategoryCreated={onCategoryCreated}
                onReviewReconciled={onReviewReconciled}
                onSuccess={onSuccess}
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
        item.sourceAccount?.name !== documentSourceAccountName
          ? item.sourceAccount?.name
          : undefined
      }
      meta={
        <ReviewItemMeta
          categories={categories}
          item={item}
          properties={properties}
        />
      }
      signals={
        item.duplicateEvidence ||
        item.existingOperationCandidates.length > 0 ||
        blockingReason ||
        problems.length > 0 ? (
          <>
            <DuplicateComparison item={item} />
            <ExistingOperationComparison
              item={item}
              onSelect={setSelectedOperationId}
              selectedOperationId={existingOperationId}
            />
            {blockingReason && item.duplicateEvidence === null ? (
              <ReviewBlockingReason reason={blockingReason} />
            ) : null}
            {problems.map((problem) => (
              <RowProblemSignal
                currency={currency}
                key={`${problem.code}-${problem.itemId}`}
                problem={problem}
              />
            ))}
          </>
        ) : undefined
      }
      state={
        (hasReviewPanel && panelOpen) || sourceOpen ? "working" : "default"
      }
      tabIndex={-1}
      value={
        amount !== null ? (
          <MoneyValue
            amount={formatMoneyAmount(amount, operationType)}
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

function ReviewItemContext({
  amount,
  currency,
  description,
  item,
}: {
  amount: string | null;
  currency: string;
  description: string;
  item: ReviewItemDto;
}) {
  const operationDate = item.normalized.operationDate
    ? formatIsoDate(item.normalized.operationDate)
    : (item.raw.operationDate ?? "Дата не распознана");

  return (
    <aside
      aria-label="Контекст текущей операции"
      className={styles.reviewItemContext}
    >
      <span className={styles.reviewItemContextLabel}>Текущая операция</span>
      <span className={styles.reviewItemContextDate}>{operationDate}</span>
      <strong className={styles.reviewItemContextDescription}>
        {description}
      </strong>
      <span
        className={styles.reviewItemContextAmount}
        data-tone={item.classification.operationType ?? "neutral"}
      >
        {amount !== null ? (
          <>
            {formatMoneyAmount(amount, item.classification.operationType)}{" "}
            <small>{currency}</small>
          </>
        ) : (
          "Сумма не распознана"
        )}
      </span>
    </aside>
  );
}
