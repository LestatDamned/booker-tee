import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { AppShell } from "../../shell/app-shell";
import { AppliedFilterSummary } from "../../ui/applied-filter-summary/applied-filter-summary";
import { BackLink } from "../../ui/back-link/back-link";
import { Badge } from "../../ui/badge/badge";
import { Button, ButtonLink, RouterButtonLink } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { MoneyValue, type MoneyTone } from "../../ui/money-value/money-value";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { StatusLabel } from "../../ui/status-label/status-label";
import { Tag, type TagTone } from "../../ui/tag/tag";
import { ToastViewport, useToastQueue } from "../../ui/toast/toast";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchStatus } from "../../ui/workbench-content/workbench-status";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import type { CategoryDetailDto } from "./api/category-detail-api";
import { CategoryEditPanel } from "./category-edit-panel";
import { CategoryLifecycleActions } from "./category-lifecycle-actions";
import { CategoryDetailFilters } from "./category-detail-filters";
import {
  CategoryOperations,
  CategoryOperationsPagination,
} from "./category-detail-operations";
import {
  categoryDetailResetTarget,
  categoryDetailApiSearch,
  categoryDetailSearchUrl,
  safeReportsReturnPath,
} from "./category-detail-query";
import { CategoryRulesPreview } from "./category-rules-preview";
import { useCategoryEditor } from "./use-category-editor";
import { useCategoryLifecycle } from "./use-category-lifecycle";
import styles from "./category-detail-page.module.css";

const kindLabels = {
  adjustment: "Корректировка",
  expense: "Расход",
  income: "Доход",
  mixed: "Смешанная",
  transfer: "Перевод",
} as const;

export function CategoryDetailPage({
  detail: initialDetail,
  navigationPending = false,
  session,
}: {
  detail: CategoryDetailDto;
  navigationPending?: boolean;
  session: SessionDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [localDetail, setLocalDetail] = useState<{
    source: CategoryDetailDto;
    value: CategoryDetailDto;
  } | null>(null);
  const detail =
    localDetail?.source === initialDetail ? localDetail.value : initialDetail;
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [archiveBlockerVisible, setArchiveBlockerVisible] = useState(false);
  const { dismissToast, showToast, toast } = useToastQueue();
  const searchParams = new URLSearchParams(location.search);
  const editor = useCategoryEditor({
    apiSearch: categoryDetailApiSearch(location.search),
    csrfToken: session.csrfToken,
    onCommitted: (value) => setLocalDetail({ source: initialDetail, value }),
    onReloaded: (value) => setLocalDetail({ source: initialDetail, value }),
    showToast,
  });
  const lifecycle = useCategoryLifecycle({
    apiSearch: categoryDetailApiSearch(location.search),
    csrfToken: session.csrfToken,
    onCommitted: (category) => {
      setArchiveBlockerVisible(false);
      setLocalDetail((current) => ({
        source: initialDetail,
        value: {
          ...(current?.source === initialDetail
            ? current.value
            : initialDetail),
          category,
        },
      }));
    },
    onDeleted: (name) => {
      void navigate("/categories?view=archived", {
        replace: true,
        state: { categoryToast: `Категория «${name}» удалена.` },
      });
    },
    onReloaded: (value) => setLocalDetail({ source: initialDetail, value }),
    showToast,
  });
  const reportsReturnPath = safeReportsReturnPath(
    searchParams.get("return_to"),
  );
  const hasExplicitCurrency = searchParams.has("currency");
  const filters = appliedFilterLabels(detail, { hasExplicitCurrency });
  const hasNarrowingFilters = Boolean(
    detail.appliedFilters.dateFrom ||
    detail.appliedFilters.dateTo ||
    detail.appliedFilters.operationType ||
    detail.appliedFilters.search ||
    hasExplicitCurrency,
  );
  const resetTarget = categoryDetailResetTarget(
    location.pathname,
    reportsReturnPath,
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("search");
    if (typeof value !== "string") return;
    void navigate(
      categoryDetailSearchUrl(location.pathname, location.search, value),
    );
  }

  return (
    <AppShell session={session}>
      <PageFrame mobileTop="compact" spacing="block">
        <WorkbenchSurface
          aria-busy={navigationPending}
          className={styles.workbench}
        >
          <WorkbenchHeader>
            <BackLink
              className={styles.backLink}
              to={reportsReturnPath ?? "/categories"}
            >
              {reportsReturnPath ? "Вернуться в отчёт" : "Все категории"}
            </BackLink>
            <PageHeader
              actions={
                <div className={styles.headerActions}>
                  <CategorySummary summary={detail.summary} />
                  <CategoryLifecycleActions
                    category={detail.category}
                    editing={Boolean(editor.editState)}
                    onArchive={() => lifecycle.requestArchive(detail.category)}
                    onArchiveBlocked={() => setArchiveBlockerVisible(true)}
                    onDelete={() => lifecycle.requestDelete(detail.category)}
                    onEdit={(trigger) => editor.beginEdit(detail, trigger)}
                    onRestore={() => lifecycle.restore(detail.category)}
                    pending={lifecycle.pending}
                  />
                </div>
              }
              description={
                detail.category.notes ??
                "Финансовый результат и подтверждённые операции категории."
              }
              eyebrow={operationCountLabel(detail.operations.total)}
              title={detail.category.name}
            />
            <div className={styles.identityMeta}>
              <Tag tone={kindTone(detail.category.kind)} variant="soft">
                {kindLabels[detail.category.kind]}
              </Tag>
              {detail.category.isSystem ? (
                <StatusLabel tone="information">
                  Системная · только чтение
                </StatusLabel>
              ) : detail.category.isActive ? (
                <StatusLabel tone="success">Активна</StatusLabel>
              ) : (
                <StatusLabel tone="neutral">В архиве</StatusLabel>
              )}
              {!detail.category.isSystem &&
              !detail.category.capabilities.canUpdate ? (
                <StatusLabel tone="neutral">Только чтение</StatusLabel>
              ) : null}
              <span>{ruleCountLabel(detail.rules.total)}</span>
            </div>
          </WorkbenchHeader>

          {archiveBlockerVisible ? (
            <InlineNotice
              action={
                <ButtonLink
                  href={`/rules?category_id=${detail.category.id}`}
                  icon="rules"
                  tone="secondary"
                >
                  Открыть правила
                </ButtonLink>
              }
              className={styles.lifecycleNotice}
              title="Сначала отключите активные правила"
              tone="warning"
            >
              {activeRuleCountLabel(detail.category.activeRuleCount)} продолжат
              предлагать эту категорию новым операциям. Правила не отключаются
              автоматически.
            </InlineNotice>
          ) : null}

          {lifecycle.failure ? (
            <InlineNotice
              action={
                <Button
                  disabled={lifecycle.pending}
                  icon="retry"
                  isLoading={lifecycle.pending}
                  onClick={() =>
                    lifecycle.failure?.conflict || lifecycle.failure?.blocked
                      ? void lifecycle.refreshAndRetry()
                      : lifecycle.retry()
                  }
                  tone="secondary"
                >
                  {lifecycle.failure.conflict || lifecycle.failure.blocked
                    ? "Обновить и повторить"
                    : "Повторить"}
                </Button>
              }
              className={styles.lifecycleNotice}
              role="alert"
              title="Не удалось изменить категорию"
              tone="danger"
            >
              {lifecycle.failure.message}
            </InlineNotice>
          ) : null}

          {!detail.category.isActive &&
          detail.category.capabilities.canUpdate &&
          !detail.category.capabilities.canDelete &&
          detail.category.deleteBlockers.reasonCodes.length > 0 ? (
            <CategoryDeleteBlockerNotice category={detail.category} />
          ) : null}

          {editor.editState ? (
            <CategoryEditPanel
              confirmation={editor.confirmation}
              editState={editor.editState}
              onCancelConfirmation={editor.cancelConfirmation}
              onChange={editor.changeDraft}
              onClose={editor.requestClose}
              onConfirmDiscard={editor.confirmDiscard}
              onConfirmKindChange={() => void editor.confirmKindChange()}
              onReload={() => void editor.reloadSnapshot()}
              onSubmit={(event) => void editor.submit(event)}
            />
          ) : null}

          <WorkbenchToolbar>
            <div className={styles.toolbarActions}>
              <WorkbenchSearch
                ariaLabel="Поиск операций категории"
                inputId="category-operation-search"
                inputLabel="Поиск по описанию операции"
                inputProps={{
                  defaultValue: detail.appliedFilters.search ?? "",
                }}
                key={detail.appliedFilters.search ?? ""}
                onSubmit={submitSearch}
                placeholder="Поиск по описанию"
              />
              <Button
                aria-controls="category-detail-filter-region"
                aria-expanded={filtersOpen}
                icon="filter"
                onClick={() => setFiltersOpen((value) => !value)}
              >
                {filtersOpen ? "Скрыть фильтры" : "Показать фильтры"}
                {filters.length ? <Badge>{filters.length}</Badge> : null}
              </Button>
            </div>
            <AppliedFilterSummary
              filters={filtersOpen ? [] : filters}
              resetTo={resetTarget}
            />
          </WorkbenchToolbar>

          {filtersOpen ? (
            <CategoryDetailFilters
              detail={detail}
              onClose={() => setFiltersOpen(false)}
              reportsReturnPath={reportsReturnPath}
            />
          ) : null}

          <WorkbenchStatus>
            {navigationPending ? "Обновляем операции…" : ""}
          </WorkbenchStatus>

          <WorkbenchContent
            aria-label="Операции категории"
            isEmpty={detail.operations.items.length === 0}
          >
            {detail.operations.items.length ? (
              <CategoryOperations detail={detail} />
            ) : (
              <WorkbenchEmptyState
                action={
                  hasNarrowingFilters ? (
                    <RouterButtonLink icon="filter" to={resetTarget}>
                      Сбросить фильтры
                    </RouterButtonLink>
                  ) : undefined
                }
                icon={hasNarrowingFilters ? "search" : "operations"}
                kind={hasNarrowingFilters ? "filtered" : "primary"}
                title={
                  hasNarrowingFilters
                    ? "По этим фильтрам операций нет"
                    : "Подтверждённых операций пока нет"
                }
              >
                {hasNarrowingFilters
                  ? "Измените условия поиска или сбросьте фильтры."
                  : "Операции появятся здесь после подтверждения в ledger."}
              </WorkbenchEmptyState>
            )}
          </WorkbenchContent>

          <CategoryOperationsPagination
            detail={detail}
            disabled={navigationPending}
          />
          <CategoryRulesPreview detail={detail} />
        </WorkbenchSurface>
      </PageFrame>
      <ToastViewport onDismiss={dismissToast} toast={toast} />

      {lifecycle.archiveCandidate ? (
        <ConfirmationDialog
          confirmLabel="Перенести в архив"
          description={`История, операции и отчёты категории «${lifecycle.archiveCandidate.name}» сохранятся. Категория исчезнет из выбора для новых операций. Связанные выключенные правила останутся без изменений.`}
          onCancel={lifecycle.cancelArchive}
          onConfirm={lifecycle.confirmArchive}
          pending={lifecycle.pending}
          title="Перенести категорию в архив?"
        />
      ) : null}

      {lifecycle.deleteCandidate ? (
        <ConfirmationDialog
          confirmLabel="Удалить категорию"
          description={`Категория «${lifecycle.deleteCandidate.name}» будет удалена без возможности восстановления. Финансовой истории и связанных данных у неё нет.`}
          onCancel={lifecycle.cancelDelete}
          onConfirm={lifecycle.confirmDelete}
          pending={lifecycle.pending}
          title="Удалить категорию навсегда?"
        />
      ) : null}
    </AppShell>
  );
}

function CategoryDeleteBlockerNotice({
  category,
}: {
  category: CategoryDetailDto["category"];
}) {
  const blockers = category.deleteBlockers;
  return (
    <InlineNotice
      action={
        blockers.ruleCount > 0 ? (
          <ButtonLink
            href={`/rules?category_id=${category.id}`}
            icon="rules"
            tone="secondary"
          >
            Открыть правила
          </ButtonLink>
        ) : undefined
      }
      className={styles.lifecycleNotice}
      title="Удаление пока недоступно"
      tone="information"
    >
      Категория останется в архиве, пока существуют связанные данные:
      <ul className={styles.blockerList}>
        {blockers.operationCount > 0 ? (
          <li>
            {operationCountLabel(blockers.operationCount)} любого состояния
          </li>
        ) : null}
        {blockers.ruleCount > 0 ? (
          <li>{ruleCountLabel(blockers.ruleCount)}</li>
        ) : null}
        {blockers.rawSuggestionCount > 0 ? (
          <li>{rawSuggestionCountLabel(blockers.rawSuggestionCount)}</li>
        ) : null}
        {blockers.childCategoryCount > 0 ? (
          <li>{childCategoryCountLabel(blockers.childCategoryCount)}</li>
        ) : null}
      </ul>
    </InlineNotice>
  );
}

function CategorySummary({
  summary,
}: {
  summary: CategoryDetailDto["summary"];
}) {
  return (
    <dl className={styles.summaryGrid}>
      <SummaryValue
        amount={summary.income}
        currency={summary.currency}
        label="Доходы"
        tone="income"
      />
      <SummaryValue
        amount={summary.expense}
        currency={summary.currency}
        label="Расходы"
        tone="expense"
      />
      <SummaryValue
        amount={summary.profit}
        currency={summary.currency}
        label="Результат"
        tone={decimalSign(summary.profit) < 0 ? "expense" : "profit"}
      />
    </dl>
  );
}

function SummaryValue({
  amount,
  currency,
  label,
  tone,
}: {
  amount: string;
  currency: string;
  label: string;
  tone: MoneyTone;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        <MoneyValue
          amount={formatMoneyAmount(amount, null)}
          currency={currency}
          size="compact"
          tone={tone}
        />
      </dd>
    </div>
  );
}

function appliedFilterLabels(
  detail: CategoryDetailDto,
  { hasExplicitCurrency }: { hasExplicitCurrency: boolean },
): string[] {
  const filters: string[] = [];
  if (detail.appliedFilters.dateFrom) {
    filters.push(`От: ${detail.appliedFilters.dateFrom}`);
  }
  if (detail.appliedFilters.dateTo) {
    filters.push(`До: ${detail.appliedFilters.dateTo}`);
  }
  if (hasExplicitCurrency) {
    filters.push(`Валюта: ${detail.appliedFilters.currency}`);
  }
  if (detail.appliedFilters.operationType) {
    filters.push(
      `Тип: ${detail.appliedFilters.operationType === "income" ? "Доход" : "Расход"}`,
    );
  }
  return filters;
}

function kindTone(kind: keyof typeof kindLabels): TagTone {
  return kind === "mixed" ? "category" : kind;
}

function decimalSign(value: string): -1 | 0 | 1 {
  const normalized = value.replace(/^[+-]/, "").replace(/[.,]/, "");
  if (/^0*$/.test(normalized)) return 0;
  return value.startsWith("-") ? -1 : 1;
}

function operationCountLabel(count: number): string {
  return `${count} ${pluralize(count, "операция", "операции", "операций")}`;
}

function ruleCountLabel(count: number): string {
  return `${count} ${pluralize(count, "правило", "правила", "правил")}`;
}

function activeRuleCountLabel(count: number): string {
  return `${count} ${pluralize(count, "активное правило", "активных правила", "активных правил")}`;
}

function rawSuggestionCountLabel(count: number): string {
  return `${count} ${pluralize(count, "импорт-предложение", "импорт-предложения", "импорт-предложений")}`;
}

function childCategoryCountLabel(count: number): string {
  return `${count} ${pluralize(count, "дочерняя категория", "дочерние категории", "дочерних категорий")}`;
}

function pluralize(count: number, one: string, few: string, many: string) {
  const tens = count % 100;
  const units = count % 10;
  if (tens >= 11 && tens <= 14) return many;
  if (units === 1) return one;
  if (units >= 2 && units <= 4) return few;
  return many;
}
