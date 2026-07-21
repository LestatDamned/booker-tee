import { useState } from "react";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { PageHeader } from "../../ui/page-header/page-header";
import { RequestState } from "../../ui/request-state/request-state";
import type { ImportReviewDto } from "./api/import-review-api";
import type { ImportReviewCategoryReferenceDto } from "./api/import-review-mutations";
import { ClassificationPanel } from "./classification-panel";
import styles from "./import-review.module.css";

type ImportReviewPageProps = {
  review: ImportReviewDto;
  session: SessionDto;
};

export function ImportReviewPage({ review, session }: ImportReviewPageProps) {
  const readonly = !review.capabilities.canWrite;
  const [categories, setCategories] = useState(review.references.categories);

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
        <div className={styles.header}>
          <PageHeader
            description={
              readonly
                ? "Этот review доступен только для чтения согласно вашей роли."
                : "Сверьте исходные и нормализованные данные перед проведением."
            }
            eyebrow={`Документ · ${review.document.status}`}
            title="Проверка импорта"
          />
          <p className={styles.filename}>{review.document.filename}</p>
        </div>

        <ReviewQueue review={review} />
        <ReviewValidation validation={review.validation} />

        <section aria-label="Строки импорта" className={styles.itemsRegion}>
          {review.items.length === 0 ? (
            <RequestState
              message="Вернитесь к документу и проверьте parsing или настройку колонок."
              status="empty"
              title="Сырых строк пока нет"
            />
          ) : (
            <ol className={styles.items}>
              {review.items.map((item) => (
                <li key={item.id}>
                  <ReviewItem
                    categories={categories}
                    documentId={review.document.id}
                    item={item}
                    onCategoryCreated={addCategory}
                    problems={
                      review.validation?.rowProblems.filter(
                        (problem) => problem.itemId === item.id,
                      ) ?? []
                    }
                    properties={review.references.properties}
                    readonly={readonly}
                    csrfToken={session.csrfToken}
                  />
                </li>
              ))}
            </ol>
          )}
        </section>
      </section>
    </AppShell>
  );
}

function ReviewValidation({
  validation,
}: {
  validation: ImportReviewDto["validation"];
}) {
  if (!validation) {
    return (
      <section className={styles.validation}>
        <p className={styles.queueLabel}>Контроль данных</p>
        <h2>Проверка ещё не рассчитана</h2>
        <p>Для документа пока нет завершённой попытки parsing.</p>
      </section>
    );
  }

  const copy = validationCopy(validation.reasonCode);
  return (
    <section
      aria-labelledby="import-review-validation-title"
      className={styles.validation}
      data-status={validation.status}
    >
      <div className={styles.validationHeader}>
        <div>
          <p className={styles.queueLabel}>Контроль данных</p>
          <h2 id="import-review-validation-title">{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <dl className={styles.validationCounts}>
          <ValidationCount
            label="Извлечено"
            value={validation.extractedCount}
          />
          <ValidationCount
            label="Нормализовано"
            value={validation.normalizedCount}
          />
          <ValidationCount
            label="Нужна проверка"
            value={validation.needsReviewCount}
          />
        </dl>
      </div>

      <div
        aria-label="Сверка контрольных итогов"
        className={styles.totalsTableRegion}
        tabIndex={0}
      >
        <table className={styles.totalsTable}>
          <caption>Суммы строк и контрольные итоги выписки</caption>
          <thead>
            <tr>
              <th scope="col">Поток</th>
              <th scope="col">По строкам</th>
              <th scope="col">Игнорируется</th>
              <th scope="col">В выписке</th>
              <th scope="col">Не объяснено</th>
            </tr>
          </thead>
          <tbody>
            <TotalsRow
              calculated={validation.calculatedTotalInflow}
              currency={validation.currency}
              ignored={validation.ignoredTotalInflow}
              label="Поступления"
              statement={validation.statementTotalInflow}
              unexplained={validation.unexplainedInflowDifference}
            />
            <TotalsRow
              calculated={validation.calculatedTotalOutflow}
              currency={validation.currency}
              ignored={validation.ignoredTotalOutflow}
              label="Списания"
              statement={validation.statementTotalOutflow}
              unexplained={validation.unexplainedOutflowDifference}
            />
          </tbody>
        </table>
      </div>

      <p className={styles.balanceChain}>
        Проверка цепочки остатков: {balanceChainLabel(validation.balanceChain)}
      </p>
    </section>
  );
}

function ValidationCount({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function TotalsRow({
  calculated,
  currency,
  ignored,
  label,
  statement,
  unexplained,
}: {
  calculated: string;
  currency: string | null;
  ignored: string;
  label: string;
  statement: string | null;
  unexplained: string | null;
}) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{moneyLabel(calculated, currency)}</td>
      <td>{moneyLabel(ignored, currency)}</td>
      <td>{moneyLabel(statement, currency)}</td>
      <td>{moneyLabel(unexplained, currency)}</td>
    </tr>
  );
}

function ReviewQueue({ review }: { review: ImportReviewDto }) {
  const { queue } = review;
  const complete = queue.total > 0 && queue.remaining === 0;
  const title =
    queue.total === 0
      ? "Строк для проверки пока нет"
      : complete
        ? "Все строки обработаны"
        : `Осталось ${queue.remaining} из ${queue.total}`;

  return (
    <section
      aria-labelledby="import-review-queue-title"
      className={styles.queue}
    >
      <div>
        <p className={styles.queueLabel}>Очередь проверки</p>
        <h2 id="import-review-queue-title">{title}</h2>
      </div>
      <div className={styles.queueProgress}>
        <span>
          {queue.completed} / {queue.total}
        </span>
        <progress max={Math.max(queue.total, 1)} value={queue.completed}>
          {queue.completed} из {queue.total}
        </progress>
      </div>
      {queue.firstRemainingItemId ? (
        <a
          className={styles.nextLink}
          href={`#raw-${queue.firstRemainingItemId}`}
        >
          К первой оставшейся строке
        </a>
      ) : null}
    </section>
  );
}

function ReviewItem({
  categories,
  documentId,
  item,
  onCategoryCreated,
  problems,
  properties,
  readonly,
  csrfToken,
}: {
  categories: ImportReviewDto["references"]["categories"];
  documentId: string;
  item: ImportReviewDto["items"][number];
  onCategoryCreated: (category: ImportReviewCategoryReferenceDto) => void;
  problems: NonNullable<ImportReviewDto["validation"]>["rowProblems"];
  properties: ImportReviewDto["references"]["properties"];
  readonly: boolean;
  csrfToken: string;
}) {
  const normalizedDescription =
    item.normalized.description ?? item.raw.description ?? "Без описания";
  const normalizedDate =
    item.normalized.operationDate ?? item.raw.operationDate ?? "—";
  const normalizedAmount = item.normalized.amount ?? item.raw.amount ?? "—";
  const currency = item.normalized.currency ?? item.raw.currency ?? "";
  return (
    <article
      className={styles.item}
      data-terminal={item.isTerminal ? "true" : "false"}
      id={`raw-${item.id}`}
      tabIndex={-1}
    >
      <header className={styles.itemHeader}>
        <div>
          <p className={styles.rowIndex}>Строка {item.rowIndex}</p>
          <h3>{normalizedDescription}</h3>
        </div>
        <div className={styles.money}>
          <strong>{normalizedAmount}</strong>
          <span>{currency}</span>
        </div>
      </header>
      <dl className={styles.summary}>
        <div>
          <dt>Дата</dt>
          <dd>{normalizedDate}</dd>
        </div>
        <div>
          <dt>Счёт</dt>
          <dd>{item.sourceAccount?.name ?? "Не определён"}</dd>
        </div>
        <div>
          <dt>Статус</dt>
          <dd>{statusLabel(item.status)}</dd>
        </div>
        <div>
          <dt>Классификация</dt>
          <dd>
            {operationTypeLabel(item.classification.operationType)} ·{" "}
            {classificationSourceLabel(item.classification.source)}
          </dd>
        </div>
      </dl>
      {problems.map((problem) => (
        <div
          className={styles.rowProblem}
          key={`${problem.code}-${problem.itemId}`}
        >
          <strong>Нарушена цепочка остатков</strong>
          <span>
            После строки {problem.previousRowIndex} ожидался остаток{" "}
            {moneyLabel(problem.expectedBalanceAfter, currency)}, получен{" "}
            {moneyLabel(problem.actualBalanceAfter, currency)}.
          </span>
        </div>
      ))}
      {!item.isTerminal ? (
        <ClassificationPanel
          categories={categories}
          csrfToken={csrfToken}
          documentId={documentId}
          item={item}
          onCategoryCreated={onCategoryCreated}
          properties={properties}
          readonly={readonly}
        />
      ) : null}
      <details className={styles.rawDetails}>
        <summary>Исходные данные</summary>
        <dl>
          <RawValue label="Дата" value={item.raw.operationDate} />
          <RawValue label="Описание" value={item.raw.description} />
          <RawValue label="Сумма" value={item.raw.amount} />
          <RawValue label="Валюта" value={item.raw.currency} />
          <RawValue label="Остаток" value={item.raw.balanceAfter} />
          <RawValue label="Подсказка счёта" value={item.raw.accountHint} />
        </dl>
      </details>
    </article>
  );
}

function validationCopy(
  reason: NonNullable<ImportReviewDto["validation"]>["reasonCode"],
): { title: string; description: string } {
  const copy: Record<typeof reason, { title: string; description: string }> = {
    totals_match: {
      title: "Контрольные итоги совпадают",
      description: "Суммы нормализованных строк согласованы с выпиской.",
    },
    rows_need_review: {
      title: "Есть строки с неопределёнными данными",
      description:
        "Сначала проверьте отмеченные строки, затем повторите сверку итогов.",
    },
    balance_chain_mismatch: {
      title: "Нарушена цепочка остатков",
      description:
        "Один или несколько остатков не следуют из соседних операций.",
    },
    control_totals_unavailable: {
      title: "Контрольные итоги недоступны",
      description:
        "Parser не извлёк суммы выписки; строки всё ещё доступны для ручной проверки.",
    },
    control_totals_mismatch: {
      title: "Итоги не совпадают с выпиской",
      description:
        "Остаётся необъяснённая разница между строками и контрольными итогами.",
    },
    ignored_rows_explain_mismatch: {
      title: "Разница объясняется игнорируемыми строками",
      description:
        "Суммы совпадают после учёта строк, исключённых из проведения.",
    },
  };
  return copy[reason];
}

function moneyLabel(value: string | null, currency: string | null): string {
  if (value === null) return "—";
  return currency ? `${value} ${currency}` : value;
}

function balanceChainLabel(
  balanceChain: NonNullable<ImportReviewDto["validation"]>["balanceChain"],
): string {
  if (balanceChain.status === "unavailable") return "недостаточно данных";
  if (balanceChain.status === "mismatch") {
    return `обнаружено несоответствий: ${balanceChain.mismatchCount}; проверено пар: ${balanceChain.checkedPairCount}`;
  }
  return `расхождений нет; проверено пар: ${balanceChain.checkedPairCount}`;
}

function operationTypeLabel(
  operationType: ImportReviewDto["items"][number]["classification"]["operationType"],
): string {
  if (operationType === null) return "Тип не определён";
  return {
    income: "Доход",
    expense: "Расход",
    transfer: "Перевод",
    adjustment: "Корректировка",
  }[operationType];
}

function classificationSourceLabel(
  source: ImportReviewDto["items"][number]["classification"]["source"],
): string {
  return {
    explicit: "выбрано вручную",
    suggested: "предложено правилом",
    inferred: "определено по сумме",
    unknown: "источник неизвестен",
  }[source];
}

function RawValue({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value ?? "—"}</dd>
    </div>
  );
}

function statusLabel(
  status: ImportReviewDto["items"][number]["status"],
): string {
  const labels: Record<ImportReviewDto["items"][number]["status"], string> = {
    extracted: "Извлечено",
    normalized: "Нормализовано",
    suggested: "Есть предложение",
    needs_review: "Нужна проверка",
    matched: "Проверено как уникальное",
    ignored: "Игнорируется",
    duplicate: "Дубль",
    possible_duplicate: "Возможный дубль",
    failed: "Ошибка",
    confirmed: "Подтверждено",
  };
  return labels[status];
}
