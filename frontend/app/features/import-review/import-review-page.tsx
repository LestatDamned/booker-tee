import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router";

import type { SessionDto } from "../../api/session";
import { revealHashTarget } from "../../shared/navigation/hash-target";
import { AppShell } from "../../shell/app-shell";
import { Button, RouterButtonLink } from "../../ui/button/button";
import { Icon } from "../../ui/icon/icon";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import {
  SelectionTabButton,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { ToastViewport, useToastQueue } from "../../ui/toast/toast";
import type { ImportReviewDto } from "./api/import-review-api";
import type { ImportReviewCategoryReferenceDto } from "./api/import-review-mutations";
import { ReviewItem } from "./review-item";
import { RuleActions } from "./rule-actions";
import {
  ReconciliationStatus,
  StatementReconciliation,
} from "./statement-reconciliation";
import styles from "./import-review-page.module.css";

type ImportReviewPageProps = {
  review: ImportReviewDto;
  session: SessionDto;
};

export function ImportReviewPage({ review, session }: ImportReviewPageProps) {
  return (
    <ImportReviewPageState
      key={review.document.id}
      review={review}
      session={session}
    />
  );
}

function ImportReviewPageState({ review, session }: ImportReviewPageProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [currentReview, setCurrentReview] = useState(review);
  const readonly = !currentReview.capabilities.canWrite;
  const [categories, setCategories] = useState(review.references.categories);
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = reviewFilterFromSearch(searchParams.get("filter"));
  const filteredReviewItems = filteredItems(currentReview, filter);
  const visibleRowCount = visibleRowCountFromSearch(searchParams.get("rows"));
  const visibleItems = filteredReviewItems.slice(0, visibleRowCount);
  const hiddenItemCount = filteredReviewItems.length - visibleItems.length;
  const [navigationAnchorId, setNavigationAnchorId] = useState<string | null>(
    null,
  );
  const { dismissToast, showToast, toast } = useToastQueue();
  const visibleItemKey = visibleItems.map((item) => item.id).join("|");

  useEffect(() => {
    if (!location.hash.startsWith("#raw-")) return;
    const itemId = location.hash.slice(5);
    const targetIndex = filteredItems(currentReview, filter).findIndex(
      (item) => item.id === itemId,
    );
    if (targetIndex < 0) return;
    if (targetIndex >= visibleRowCount) {
      const nextSearchParams = new URLSearchParams(searchParams);
      nextSearchParams.set(
        "rows",
        String(
          Math.ceil((targetIndex + 1) / VISIBLE_ROW_STEP) * VISIBLE_ROW_STEP,
        ),
      );
      void navigate(
        {
          pathname: location.pathname,
          search: `?${nextSearchParams.toString()}`,
          hash: location.hash,
        },
        { preventScrollReset: true, replace: true },
      );
      return;
    }
    const animationFrame = window.requestAnimationFrame(() => {
      const target = document.getElementById(`raw-${itemId}`);
      if (target instanceof HTMLElement) revealHashTarget(target);
    });
    return () => window.cancelAnimationFrame(animationFrame);
  }, [
    currentReview,
    filter,
    location.hash,
    location.pathname,
    navigate,
    searchParams,
    setSearchParams,
    visibleRowCount,
  ]);

  useEffect(() => {
    let animationFrame = 0;
    const visibleItemIds = visibleItemKey ? visibleItemKey.split("|") : [];

    function updateAnchorFromViewport() {
      const viewportMarker = 64;
      const visibleRows = visibleItemIds
        .map((id) => ({
          id,
          row: document.getElementById(`raw-${id}`),
        }))
        .filter(
          (
            candidate,
          ): candidate is {
            id: string;
            row: HTMLElement;
          } => candidate.row instanceof HTMLElement,
        )
        .map(({ id, row }) => ({ id, rect: row.getBoundingClientRect() }))
        .filter(({ rect }) => rect.bottom > viewportMarker);
      const current =
        visibleRows.find(
          ({ rect }) =>
            rect.top <= viewportMarker && rect.bottom > viewportMarker,
        ) ?? visibleRows[0];
      if (current) setNavigationAnchorId(current.id);
    }

    function scheduleViewportUpdate() {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(updateAnchorFromViewport);
    }

    updateAnchorFromViewport();
    window.addEventListener("scroll", scheduleViewportUpdate, {
      passive: true,
    });
    window.addEventListener("resize", scheduleViewportUpdate);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener("scroll", scheduleViewportUpdate);
      window.removeEventListener("resize", scheduleViewportUpdate);
    };
  }, [visibleItemKey]);

  function changeFilter(nextFilter: ReviewFilter) {
    const nextSearchParams = new URLSearchParams(searchParams);
    if (nextFilter === "all") {
      nextSearchParams.delete("filter");
    } else {
      nextSearchParams.set("filter", nextFilter);
    }
    nextSearchParams.delete("rows");
    setSearchParams(nextSearchParams, { preventScrollReset: true });
  }

  function navigateToReviewItem(itemId: string) {
    const targetIndex = filteredReviewItems.findIndex(
      (item) => item.id === itemId,
    );
    if (targetIndex >= visibleRowCount) {
      const nextSearchParams = new URLSearchParams(searchParams);
      const requiredRowCount =
        Math.ceil((targetIndex + 1) / VISIBLE_ROW_STEP) * VISIBLE_ROW_STEP;
      nextSearchParams.set("rows", String(requiredRowCount));
      setSearchParams(nextSearchParams, { preventScrollReset: true });
    }
    setNavigationAnchorId(itemId);
    window.setTimeout(() => {
      const target = document.getElementById(`raw-${itemId}`);
      target?.focus({ preventScroll: true });
      target?.scrollIntoView({ block: "nearest" });
    });
  }

  function showMoreRows() {
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set(
      "rows",
      String(
        Math.min(
          visibleRowCount + VISIBLE_ROW_STEP,
          filteredReviewItems.length,
        ),
      ),
    );
    setSearchParams(nextSearchParams, { preventScrollReset: true });
  }

  function reconcileReview(nextReview: ImportReviewDto) {
    setCurrentReview(nextReview);
    setCategories(nextReview.references.categories);
  }

  function addCategory(category: ImportReviewCategoryReferenceDto) {
    setCategories((current) =>
      [...current.filter((item) => item.id !== category.id), category].sort(
        (left, right) => left.name.localeCompare(right.name, "ru"),
      ),
    );
  }

  return (
    <AppShell session={session}>
      <PageFrame className={styles.page} spacing="none">
        <WorkbenchSurface aria-label="Сводка проверки импорта">
          <header className={styles.summaryHeader}>
            <div className={styles.summaryIdentity}>
              <p className={styles.sectionEyebrow}>
                Документ · {documentStatusLabel(currentReview.document.status)}
              </p>
              <h1>Проверка выписки</h1>
              <p className={styles.documentContext}>
                <strong>{currentReview.document.filename}</strong>
                <span aria-hidden="true"> · </span>
                {currentReview.document.sourceAccount?.name ??
                  "Счёт не определён"}
              </p>
            </div>
            <RuleActions
              csrfToken={session.csrfToken}
              documentId={currentReview.document.id}
              onReviewReconciled={reconcileReview}
              onSuccess={(message) => showToast({ message })}
              readonly={readonly}
            />
          </header>
          {readonly ? (
            <InlineNotice
              className={styles.reviewReadonlyNotice}
              title="Доступно только для чтения"
              tone="information"
            >
              Изменение и подтверждение операций недоступны для вашей роли.
            </InlineNotice>
          ) : null}
          <div className={styles.summaryBody}>
            <ReconciliationStatus validation={currentReview.validation} />
            <StatementReconciliation validation={currentReview.validation} />
          </div>
        </WorkbenchSurface>

        <WorkbenchSurface
          aria-label="Строки импорта"
          className={styles.itemsRegion}
        >
          <ReviewNavigator
            anchorItemId={navigationAnchorId}
            filter={filter}
            onNavigate={navigateToReviewItem}
            review={currentReview}
          />
          {currentReview.items.length > 0 ? (
            <div className={styles.queueToolbar}>
              <ReviewFilters
                filter={filter}
                onChange={changeFilter}
                review={currentReview}
              />
            </div>
          ) : null}
          {currentReview.items.length === 0 ? (
            <WorkbenchEmptyState
              action={
                <RouterButtonLink
                  icon="back"
                  to={`/app/imports/documents/${currentReview.document.id}`}
                >
                  Вернуться к документу
                </RouterButtonLink>
              }
              icon="imports"
              title="Операций для проверки пока нет"
            >
              Вернитесь к документу и проверьте результат распознавания.
            </WorkbenchEmptyState>
          ) : (
            <ol className={styles.items}>
              {visibleItems.map((item) => (
                <li
                  key={item.id}
                  onFocusCapture={() => setNavigationAnchorId(item.id)}
                  onPointerDown={() => setNavigationAnchorId(item.id)}
                >
                  <ReviewItem
                    categories={categories}
                    documentId={currentReview.document.id}
                    documentSourceAccountName={
                      currentReview.document.sourceAccount?.name ?? null
                    }
                    item={item}
                    onCategoryCreated={addCategory}
                    onReviewReconciled={reconcileReview}
                    onSuccess={(message) => showToast({ message })}
                    problems={
                      currentReview.validation?.rowProblems.filter(
                        (problem) => problem.itemId === item.id,
                      ) ?? []
                    }
                    properties={currentReview.references.properties}
                    readonly={readonly}
                    csrfToken={session.csrfToken}
                  />
                </li>
              ))}
              {visibleItems.length === 0 ? (
                <li>
                  <WorkbenchEmptyState
                    action={
                      <Button icon="filter" onClick={() => changeFilter("all")}>
                        Показать все строки
                      </Button>
                    }
                    icon="search"
                    kind="filtered"
                    title={filterEmptyCopy[filter].title}
                  >
                    {filterEmptyCopy[filter].message}
                  </WorkbenchEmptyState>
                </li>
              ) : null}
            </ol>
          )}
          {hiddenItemCount > 0 ? (
            <div className={styles.queueMore}>
              <p>
                Показано {visibleItems.length} из {filteredReviewItems.length}
              </p>
              <Button onClick={showMoreRows} tone="secondary">
                Показать ещё {Math.min(VISIBLE_ROW_STEP, hiddenItemCount)}
              </Button>
            </div>
          ) : null}
        </WorkbenchSurface>
      </PageFrame>
      <ToastViewport onDismiss={dismissToast} toast={toast} />
    </AppShell>
  );
}

function ReviewNavigator({
  anchorItemId,
  filter,
  onNavigate,
  review,
}: {
  anchorItemId: string | null;
  filter: ReviewFilter;
  onNavigate: (itemId: string) => void;
  review: ImportReviewDto;
}) {
  const { queue } = review;
  const itemsById = new Map(review.items.map((item) => [item.id, item]));
  const anchorIndex =
    anchorItemId === null ? -1 : queue.orderedItemIds.indexOf(anchorItemId);
  const previousItemId =
    anchorIndex < 0
      ? null
      : ([...queue.orderedItemIds]
          .slice(0, anchorIndex)
          .reverse()
          .find((id) => !itemsById.get(id)?.isTerminal) ?? null);
  const nextItemId =
    queue.orderedItemIds
      .slice(anchorIndex + 1)
      .find((id) => !itemsById.get(id)?.isTerminal) ?? null;
  const navigationAvailable = filter === "all" || filter === "pending";
  const title =
    queue.total === 0
      ? "Строк для проверки пока нет"
      : queue.remaining === 0
        ? "Все строки обработаны"
        : `${queue.completed} из ${queue.total} разобрано`;

  return (
    <section
      aria-labelledby="import-review-queue-title"
      className={styles.queue}
    >
      <div className={styles.queueProgressSummary}>
        <div className={styles.queueMetric}>
          <p>Прогресс</p>
          <h2 id="import-review-queue-title">{title}</h2>
        </div>
        <div aria-label="Прогресс проверки" className={styles.queueProgress}>
          <progress max={Math.max(queue.total, 1)} value={queue.completed}>
            {queue.completed} из {queue.total}
          </progress>
        </div>
      </div>
      <div className={styles.queueDecision}>
        <div
          aria-label="Требуют решения"
          className={styles.queueDecisionMetric}
        >
          <p>Требуют решения</p>
          <strong>{queue.remaining}</strong>
        </div>
        {navigationAvailable ? (
          <div
            aria-label="Навигация по нерешённым строкам"
            className={styles.queueNavigation}
          >
            <button
              aria-label="Предыдущая нерешённая строка"
              disabled={previousItemId === null}
              onClick={() => {
                if (previousItemId) onNavigate(previousItemId);
              }}
              type="button"
            >
              <Icon className={styles.queueNavigationUp} name="expand" />
              <span>Выше</span>
            </button>
            <button
              aria-label="Следующая нерешённая строка"
              disabled={nextItemId === null}
              onClick={() => {
                if (nextItemId) onNavigate(nextItemId);
              }}
              type="button"
            >
              <Icon name="expand" />
              <span>Ниже</span>
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}

type ReviewFilter = "all" | "pending" | "suggestions" | "problems" | "complete";
const VISIBLE_ROW_STEP = 50;

function reviewFilterFromSearch(value: string | null): ReviewFilter {
  if (
    value === "pending" ||
    value === "suggestions" ||
    value === "problems" ||
    value === "complete"
  ) {
    return value;
  }
  return "all";
}

function visibleRowCountFromSearch(value: string | null): number {
  if (value === null) return VISIBLE_ROW_STEP;
  const parsed = Number.parseInt(value, 10);
  if (!Number.isSafeInteger(parsed) || parsed < VISIBLE_ROW_STEP) {
    return VISIBLE_ROW_STEP;
  }
  return parsed;
}

function ReviewFilters({
  filter,
  onChange,
  review,
}: {
  filter: ReviewFilter;
  onChange: (filter: ReviewFilter) => void;
  review: ImportReviewDto;
}) {
  const problemIds = new Set(
    review.validation?.rowProblems.map((problem) => problem.itemId) ?? [],
  );
  const filters: Array<{ label: string; value: ReviewFilter; count: number }> =
    [
      { label: "Все", value: "all", count: review.items.length },
      {
        label: "Требуют решения",
        value: "pending",
        count: review.items.filter((item) => !item.isTerminal).length,
      },
      {
        label: "Предложения",
        value: "suggestions",
        count: review.items.filter((item) => item.ruleSuggestion.isActive)
          .length,
      },
      {
        label: "Проблемы",
        value: "problems",
        count: review.items.filter((item) => problemIds.has(item.id)).length,
      },
      {
        label: "Завершённые",
        value: "complete",
        count: review.items.filter((item) => item.isTerminal).length,
      },
    ];
  return (
    <SelectionTabs aria-label="Фильтр строк выписки" role="group">
      {filters.map((candidate) => (
        <SelectionTabButton
          count={candidate.count}
          key={candidate.value}
          onClick={() => onChange(candidate.value)}
          selected={candidate.value === filter}
        >
          {candidate.label}
        </SelectionTabButton>
      ))}
    </SelectionTabs>
  );
}

const filterEmptyCopy: Record<
  ReviewFilter,
  { message: string; title: string }
> = {
  pending: {
    title: "Нет строк, требующих решения",
    message: "Все строки обработаны. Завершённые операции доступны отдельно.",
  },
  suggestions: {
    title: "Нет предложений",
    message: "Правила пока не предложили решений для строк этой выписки.",
  },
  problems: {
    title: "Нет проблемных строк",
    message: "В строках выписки не найдено проблем сверки.",
  },
  complete: {
    title: "Нет завершённых строк",
    message:
      "Проведённые, исключённые и отмеченные дублями строки появятся здесь.",
  },
  all: {
    title: "В выписке нет строк",
    message: "Вернитесь к документу и проверьте результат распознавания.",
  },
};

function filteredItems(review: ImportReviewDto, filter: ReviewFilter) {
  if (filter === "pending")
    return review.items.filter((item) => !item.isTerminal);
  if (filter === "suggestions") {
    return review.items.filter((item) => item.ruleSuggestion.isActive);
  }
  if (filter === "problems") {
    const problemIds = new Set(
      review.validation?.rowProblems.map((problem) => problem.itemId) ?? [],
    );
    return review.items.filter((item) => problemIds.has(item.id));
  }
  if (filter === "complete")
    return review.items.filter((item) => item.isTerminal);
  return review.items;
}

function documentStatusLabel(
  status: ImportReviewDto["document"]["status"],
): string {
  return {
    uploaded: "загружен",
    pending_parse: "ожидает обработки",
    parsing: "обрабатывается",
    parsed: "распознан",
    requires_review: "нужна проверка",
    failed_to_parse: "не удалось обработать",
    imported: "импортирован",
    ignored: "игнорируется",
  }[status];
}
