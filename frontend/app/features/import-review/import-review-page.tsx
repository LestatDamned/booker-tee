import { useState } from "react";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { RequestState } from "../../ui/request-state/request-state";
import type { ImportReviewDto } from "./api/import-review-api";
import type { ImportReviewCategoryReferenceDto } from "./api/import-review-mutations";
import { ReviewItem } from "./review-item";
import { RuleActions } from "./rule-actions";
import { StatementReconciliation } from "./statement-reconciliation";
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
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const visibleItems = filteredItems(currentReview, filter);

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
            <ReviewQueue review={currentReview} />
            <StatementReconciliation validation={currentReview.validation} />
          </div>
        </section>

        <section aria-label="Строки импорта" className={styles.itemsRegion}>
          {currentReview.items.length > 0 ? (
            <div className={styles.queueToolbar}>
              <ReviewFilters
                filter={filter}
                onChange={setFilter}
                review={currentReview}
              />
            </div>
          ) : null}
          {currentReview.items.length === 0 ? (
            <RequestState
              message="Вернитесь к документу и проверьте парсинг или настройку колонок."
              status="empty"
              title="Сырых строк пока нет"
            />
          ) : (
            <ol className={styles.items}>
              {visibleItems.map((item) => (
                <li key={item.id}>
                  <ReviewItem
                    categories={categories}
                    documentId={currentReview.document.id}
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
                    message="Выберите другой фильтр, чтобы увидеть остальные строки выписки."
                    status="empty"
                    title="В этом фильтре строк нет"
                  />
                </li>
              ) : null}
            </ol>
          )}
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
      <div className={styles.queueMetric}>
        <p>Прогресс</p>
        <h2 id="import-review-queue-title">{title}</h2>
      </div>
      <div aria-label="Прогресс проверки" className={styles.queueProgress}>
        <progress max={Math.max(queue.total, 1)} value={queue.completed}>
          {queue.completed} из {queue.total}
        </progress>
      </div>
      <div aria-label="Требуют решения" className={styles.queueMetric}>
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
    </section>
  );
}

type ReviewFilter = "all" | "pending" | "suggestions" | "problems" | "complete";

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
      { label: "Все", value: "all", count: review.items.length },
      {
        label: "Проведено",
        value: "complete",
        count: review.items.filter((item) => item.isTerminal).length,
      },
      {
        label: "С предложениями",
        value: "suggestions",
        count: review.items.filter((item) => item.ruleSuggestion.isActive)
          .length,
      },
      {
        label: "Проблемы",
        value: "problems",
        count: review.items.filter((item) => problemIds.has(item.id)).length,
      },
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
    pending_parse: "ожидает парсинга",
    parsing: "обрабатывается",
    parsed: "распознан",
    requires_review: "нужна проверка",
    failed_to_parse: "ошибка парсинга",
    imported: "импортирован",
    ignored: "игнорируется",
  }[status];
}
