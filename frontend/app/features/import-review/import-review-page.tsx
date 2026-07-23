import { useState } from "react";
import { useSearchParams } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { Button } from "../../ui/button/button";
import { RequestState } from "../../ui/request-state/request-state";
import type { ImportReviewDto } from "./api/import-review-api";
import type { ImportReviewCategoryReferenceDto } from "./api/import-review-mutations";
import { ReviewItem } from "./review-item";
import { RuleActions } from "./rule-actions";
import {
  ReconciliationStatus,
  StatementReconciliation,
} from "./statement-reconciliation";
import styles from "./import-review.module.css";

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
  const [currentReview, setCurrentReview] = useState(review);
  const readonly = !currentReview.capabilities.canWrite;
  const [categories, setCategories] = useState(review.references.categories);
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = reviewFilterFromSearch(searchParams.get("filter"));
  const filteredReviewItems = filteredItems(currentReview, filter);
  const visibleRowCount = visibleRowCountFromSearch(searchParams.get("rows"));
  const visibleItems = filteredReviewItems.slice(0, visibleRowCount);
  const hiddenItemCount = filteredReviewItems.length - visibleItems.length;

  function changeFilter(nextFilter: ReviewFilter) {
    const nextSearchParams = new URLSearchParams(searchParams);
    if (nextFilter === "pending") {
      nextSearchParams.delete("filter");
    } else {
      nextSearchParams.set("filter", nextFilter);
    }
    nextSearchParams.delete("rows");
    setSearchParams(nextSearchParams, { preventScrollReset: true });
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
      <section className={styles.page}>
        <section className={styles.reviewSummary}>
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
              {readonly ? (
                <p className={styles.readonlyNotice}>
                  Доступно только для чтения.
                </p>
              ) : null}
            </div>
            <RuleActions
              csrfToken={session.csrfToken}
              documentId={currentReview.document.id}
              onReviewReconciled={reconcileReview}
              readonly={readonly}
            />
          </header>
          <div className={styles.summaryBody}>
            <div className={styles.summaryControlStrip}>
              <ReviewQueue review={currentReview} />
              <ReconciliationStatus validation={currentReview.validation} />
            </div>
            <StatementReconciliation validation={currentReview.validation} />
          </div>
        </section>

        <section aria-label="Строки импорта" className={styles.itemsRegion}>
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
            <RequestState
              message="Вернитесь к документу и проверьте результат распознавания."
              status="empty"
              title="Операций для проверки пока нет"
            />
          ) : (
            <ol className={styles.items}>
              {visibleItems.map((item) => (
                <li key={item.id}>
                  <ReviewItem
                    categories={categories}
                    documentId={currentReview.document.id}
                    documentSourceAccountName={
                      currentReview.document.sourceAccount?.name ?? null
                    }
                    item={item}
                    onCategoryCreated={addCategory}
                    onReviewReconciled={reconcileReview}
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
                <li className={styles.filterEmpty}>
                  <RequestState
                    message={filterEmptyCopy[filter].message}
                    status="empty"
                    title={filterEmptyCopy[filter].title}
                  />
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
        </section>
      </section>
    </AppShell>
  );
}

function ReviewQueue({ review }: { review: ImportReviewDto }) {
  const { queue } = review;
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
        {queue.firstRemainingItemId ? (
          <a
            className={styles.nextLink}
            href={`#raw-${queue.firstRemainingItemId}`}
          >
            Следующая нерешённая строка
          </a>
        ) : null}
      </div>
    </section>
  );
}

type ReviewFilter = "all" | "pending" | "suggestions" | "problems" | "complete";
const VISIBLE_ROW_STEP = 50;

function reviewFilterFromSearch(value: string | null): ReviewFilter {
  if (
    value === "all" ||
    value === "suggestions" ||
    value === "problems" ||
    value === "complete"
  ) {
    return value;
  }
  return "pending";
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
      { label: "Все строки", value: "all", count: review.items.length },
    ];
  return (
    <div
      aria-label="Фильтр строк выписки"
      className={styles.reviewFilters}
      role="group"
    >
      {filters.map((candidate) => (
        <button
          aria-pressed={candidate.value === filter}
          key={candidate.value}
          onClick={() => onChange(candidate.value)}
          type="button"
        >
          {candidate.label} <span>{candidate.count}</span>
        </button>
      ))}
    </div>
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
