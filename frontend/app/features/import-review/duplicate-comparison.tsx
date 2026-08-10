import { Link } from "react-router";

import { formatIsoDate } from "../../shared/date/format-date";
import type { ImportReviewDto } from "./api/import-review-api";
import styles from "./duplicate-comparison.module.css";

type ReviewItemDto = ImportReviewDto["items"][number];

export function DuplicateComparison({ item }: { item: ReviewItemDto }) {
  const evidence = item.duplicateEvidence;
  if (
    (item.status !== "duplicate" && item.status !== "possible_duplicate") ||
    evidence === null
  ) {
    return null;
  }
  const exact = evidence.reasonCode === "same_dedupe_hash";

  const currentDate = item.normalized.operationDate ?? item.raw.operationDate;
  const currentAmount = item.normalized.amount ?? item.raw.amount;
  const currency = item.normalized.currency ?? item.raw.currency ?? "";
  const candidate = evidence.candidate;

  return (
    <section
      aria-labelledby={`duplicate-comparison-${item.id}`}
      className={styles.duplicateComparison}
    >
      <header>
        <div>
          <span>{exact ? "Повторный импорт" : "Проверка совпадения"}</span>
          <h3 id={`duplicate-comparison-${item.id}`}>
            {exact ? "Уже импортировано" : "Возможный дубль"}
          </h3>
        </div>
        <p>{duplicateReason(evidence)}</p>
      </header>
      <div className={styles.duplicatePair}>
        <DuplicateFacts
          amount={currentAmount}
          currency={currency}
          date={currentDate}
          description={
            item.normalized.description ??
            item.raw.description ??
            "Без описания"
          }
          label={exact ? "Повторная строка" : "Текущая строка"}
        />
        <DuplicateFacts
          amount={candidate.amount}
          currency={candidate.currency}
          date={candidate.operationDate}
          description={candidate.description ?? "Без описания"}
          label={exact ? "Импортировано ранее" : "Найденный кандидат"}
        >
          <Link to={`/imports/documents/${candidate.documentId}`}>
            {candidate.documentFilename}
          </Link>
          {candidate.operationId ? (
            <Link
              to={`/imports/documents/${candidate.documentId}/review#raw-${candidate.itemId}`}
            >
              Открыть проведённую операцию
            </Link>
          ) : null}
        </DuplicateFacts>
      </div>
    </section>
  );
}

function DuplicateFacts({
  amount,
  children,
  currency,
  date,
  description,
  label,
}: {
  amount: string | null;
  children?: React.ReactNode;
  currency: string;
  date: string | null;
  description: string;
  label: string;
}) {
  return (
    <article className={styles.duplicateFacts}>
      <span>{label}</span>
      <strong>{description}</strong>
      <dl>
        <div>
          <dt>Дата</dt>
          <dd>{date ? formatIsoDate(date) : "Не определена"}</dd>
        </div>
        <div>
          <dt>Сумма</dt>
          <dd className={styles.duplicateAmount}>
            {amount
              ? `${formatDuplicateAmount(amount)} ${currency}`
              : "Не определена"}
          </dd>
        </div>
      </dl>
      {children ? (
        <div className={styles.duplicateSource}>{children}</div>
      ) : null}
    </article>
  );
}

function duplicateReason(
  evidence: NonNullable<ReviewItemDto["duplicateEvidence"]>,
): string {
  if (evidence.reasonCode === "same_dedupe_hash") {
    return "Эта банковская строка уже присутствует в другом документе.";
  }
  if (evidence.reasonCode !== "same_account_date_amount_currency") {
    return "Backend отметил строки как возможное совпадение.";
  }
  const labels = evidence.matchingFields.map(
    (field) => matchingFieldLabel[field],
  );
  return `Совпали: ${labels.join(", ")}.`;
}

const matchingFieldLabel = {
  account: "счёт",
  operation_date: "дата",
  amount: "сумма",
  currency: "валюта",
} satisfies Record<
  NonNullable<ReviewItemDto["duplicateEvidence"]>["matchingFields"][number],
  string
>;

function formatDuplicateAmount(value: string): string {
  const normalized = value.trim().replace(",", ".");
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(normalized);
  if (!match) return value;
  const integer = (match[2] ?? "0").replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const fraction = (match[3] ?? "").padEnd(2, "0").slice(0, 2);
  const sign = match[1] === "-" ? "−" : (match[1] ?? "");
  return `${sign}${integer},${fraction}`;
}
