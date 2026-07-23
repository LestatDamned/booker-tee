import { formatIsoDate } from "../../shared/date/format-date";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { StatusLabel } from "../../ui/status-label/status-label";
import type { ImportReviewDto } from "./api/import-review-api";
import styles from "./review-item.module.css";

type ReviewItemDto = ImportReviewDto["items"][number];

export function SourceSummary({
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
            {formatMoneyAmount(item.normalized.balanceAfter, null)} {currency}
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

export function SourceComparison({
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
            <StatusLabel tone="warning" variant="soft">
              Есть изменения
            </StatusLabel>
          ) : (
            <StatusLabel showIcon={false} tone="neutral">
              Без изменений
            </StatusLabel>
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
          <dt>После обработки</dt>
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
