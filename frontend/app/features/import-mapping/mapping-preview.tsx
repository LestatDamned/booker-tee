import type { RefObject } from "react";

import { MoneyValue, type MoneyTone } from "../../ui/money-value/money-value";
import { StatusLabel } from "../../ui/status-label/status-label";
import type { ImportMappingPreviewDto } from "./api/import-mapping-api";
import styles from "./import-mapping-page.module.css";

export function MappingPreview({
  headingRef,
  preview,
  stale,
}: {
  headingRef: RefObject<HTMLHeadingElement | null>;
  preview: ImportMappingPreviewDto | null;
  stale: boolean;
}) {
  if (!preview) {
    return (
      <section
        className={`${styles.previewPanel} ${styles.previewEmpty}`}
        aria-labelledby="preview-title"
      >
        <div>
          <span className={styles.sectionLabel}>Результат</span>
          <h2 id="preview-title">Предпросмотр строк</h2>
        </div>
        <p>
          Настройте обязательные роли и запустите проверку. Официальный учёт на
          этом шаге не изменится.
        </p>
      </section>
    );
  }
  const status = previewStatus(preview, stale);

  return (
    <section className={styles.previewPanel} aria-labelledby="preview-title">
      <header className={styles.previewHeader}>
        <div>
          <span className={styles.sectionLabel}>Результат</span>
          <h2 id="preview-title" ref={headingRef} tabIndex={-1}>
            Предпросмотр строк
          </h2>
        </div>
        <StatusLabel tone={status.tone} variant="soft">
          {status.label}
        </StatusLabel>
      </header>

      {stale ? (
        <div className={styles.staleNotice} role="status">
          Настройка колонок изменилась. Строки ниже относятся к предыдущему
          предпросмотру.
        </div>
      ) : null}

      {preview.warnings.length > 0 ? (
        <div className={styles.warningList} aria-live="polite">
          {preview.warnings.map((warning) => (
            <div
              className={styles.warningItem}
              data-severity={warning.severity}
              key={warning.code}
            >
              <p>{mappingWarningMessage(warning)}</p>
              {warning.fields.includes("unsignedAmountDirection") ? (
                <button
                  type="button"
                  onClick={() => focusMappingField("unsignedAmountDirection")}
                >
                  Изменить правило
                </button>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <dl className={styles.previewMetrics}>
        <div>
          <dt>Найдено</dt>
          <dd>{preview.totalRowCount}</dd>
        </div>
        <div data-tone="success">
          <dt>Корректно</dt>
          <dd>{preview.validRowCount}</dd>
        </div>
        <div data-tone={preview.invalidRowCount > 0 ? "danger" : "neutral"}>
          <dt>С ошибками</dt>
          <dd>{preview.invalidRowCount}</dd>
        </div>
        <div>
          <dt>Таблиц</dt>
          <dd>{preview.compatibleTables.length}</dd>
        </div>
      </dl>

      {preview.controlTotals.length > 0 ? (
        <section
          aria-labelledby="balance-reconciliation-title"
          className={styles.balanceReconciliation}
        >
          <header>
            <div>
              <span className={styles.sectionLabel}>Контроль</span>
              <h3 id="balance-reconciliation-title">Цепочка остатков</h3>
            </div>
            <StatusLabel
              tone={
                preview.reconciliation?.matches === true
                  ? "success"
                  : preview.reconciliation
                    ? "warning"
                    : "neutral"
              }
              variant="soft"
            >
              {preview.reconciliation?.matches === true
                ? "Совпадает"
                : preview.reconciliation
                  ? "Есть расхождение"
                  : "Нужны оба остатка"}
            </StatusLabel>
          </header>
          {preview.reconciliation ? (
            <dl>
              <div>
                <dt>Баланс на начало выписки</dt>
                <dd>
                  {formatControlMoney(
                    preview.reconciliation.openingBalance,
                    preview.controlTotals[0]?.currency ?? "RUB",
                  )}
                </dd>
              </div>
              <div>
                <dt>Изменение баланса по операциям</dt>
                <dd>
                  {formatControlMoney(
                    preview.reconciliation.movement,
                    preview.controlTotals[0]?.currency ?? "RUB",
                  )}
                </dd>
              </div>
              <div>
                <dt>Баланс на конец по расчёту</dt>
                <dd>
                  {formatControlMoney(
                    preview.reconciliation.calculatedClosingBalance,
                    preview.controlTotals[0]?.currency ?? "RUB",
                  )}
                </dd>
              </div>
              <div>
                <dt>Баланс на конец выписки</dt>
                <dd>
                  {formatControlMoney(
                    preview.reconciliation.statementClosingBalance,
                    preview.controlTotals[0]?.currency ?? "RUB",
                  )}
                </dd>
              </div>
            </dl>
          ) : (
            <p>
              Выбран один контрольный остаток. Для полной сверки укажите второй,
              если он есть в выписке.
            </p>
          )}
          {preview.reconciliation && !preview.reconciliation.matches ? (
            <p className={styles.reconciliationWarning} role="status">
              Расхождение{" "}
              {formatControlMoney(
                preview.reconciliation.difference,
                preview.controlTotals[0]?.currency ?? "RUB",
              )}
              . Проверьте выбранные остатки и направление сумм.
            </p>
          ) : null}
        </section>
      ) : null}

      {preview.rows.length > 0 ? (
        <ol className={styles.previewRows}>
          {preview.rows.map((row) => (
            <li
              data-status={row.status}
              key={`${row.tableRef.pageNumber}:${row.tableRef.tableIndex}:${row.sourceRowNumber}`}
            >
              <article>
                <div className={styles.previewRowFacts}>
                  <time dateTime={row.operationDate ?? undefined}>
                    {formatDate(row.operationDate, row.operationDateRaw)}
                  </time>
                  <span className={styles.previewSource}>
                    стр. {row.tableRef.pageNumber} · строка{" "}
                    {row.sourceRowNumber}
                  </span>
                  <StatusLabel
                    tone={row.status === "valid" ? "success" : "danger"}
                    variant="plain"
                  >
                    {row.status === "valid" ? "Корректно" : "Ошибка"}
                  </StatusLabel>
                  <MoneyValue
                    amount={formatPreviewAmount(
                      row.amount,
                      row.amountRaw,
                      row.currency,
                    )}
                    currency={row.currency}
                    tone={previewAmountTone(row.amount)}
                  />
                </div>
                <p className={styles.previewDescription}>
                  {row.description || "Описание не определено"}
                </p>
                {row.postingDate || row.postingDateRaw ? (
                  <p className={styles.secondaryFact}>
                    Дата проводки:{" "}
                    {formatDate(row.postingDate, row.postingDateRaw)}
                  </p>
                ) : null}
              </article>
              {row.errorCodes.length > 0 ? (
                <ul className={styles.rowErrors}>
                  {row.errorCodes.map((code) => (
                    <li key={code}>{mappingRowErrorMessage(code)}</li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <p className={styles.noPreviewRows}>
          По этой схеме не найдено строк для отображения.
        </p>
      )}

      {preview.rowsTruncated ? (
        <p className={styles.boundedNote}>
          Показано {preview.rows.length} из {preview.totalRowCount} строк.
          Полные итоги рассчитаны по всему документу.
        </p>
      ) : null}
    </section>
  );
}

function formatControlMoney(amount: string, currency: string): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return `${amount} ${currency}`;
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    signDisplay: "auto",
  }).format(value);
}

function formatDate(normalized: string | null, raw: string): string {
  if (!normalized) return raw || "Дата не определена";
  return new Intl.DateTimeFormat("ru-RU", { timeZone: "UTC" }).format(
    new Date(`${normalized}T00:00:00Z`),
  );
}

function previewAmountTone(amount: string | null): MoneyTone {
  const parsed = parseAmount(amount);
  if (parsed === null || parsed === 0) return "neutral";
  return parsed > 0 ? "income" : "expense";
}

function formatPreviewAmount(
  amount: string | null,
  raw: string,
  currency: string,
): string {
  const normalizedAmount = parseAmount(amount);
  const parsed = normalizedAmount ?? parseRawAmount(raw);
  if (parsed === null) return rawAmountWithoutCurrency(raw, currency) || "—";
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    signDisplay: normalizedAmount === null ? "auto" : "exceptZero",
  }).format(parsed);
}

function parseAmount(amount: string | null): number | null {
  if (!amount) return null;
  const parsed = Number(amount.replace(",", "."));
  if (!Number.isFinite(parsed)) return null;
  return parsed;
}

function parseRawAmount(raw: string): number | null {
  const compact = raw
    .replaceAll("\u00a0", "")
    .replaceAll("\u202f", "")
    .replace(/\s/gu, "")
    .replace(/[^\d,.+()-]/gu, "");
  if (!compact) return null;
  const negativeParentheses = compact.startsWith("(") && compact.endsWith(")");
  const unsigned = compact.replace(/[()+-]/gu, "");
  const commaIndex = unsigned.lastIndexOf(",");
  const dotIndex = unsigned.lastIndexOf(".");
  const decimalIndex = Math.max(commaIndex, dotIndex);
  const normalized =
    decimalIndex < 0
      ? unsigned
      : `${unsigned.slice(0, decimalIndex).replace(/[,.]/gu, "")}.${unsigned.slice(decimalIndex + 1)}`;
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) return null;
  return negativeParentheses || compact.startsWith("-") ? -parsed : parsed;
}

function rawAmountWithoutCurrency(raw: string, currency: string): string {
  return raw
    .replace(new RegExp(escapeRegExp(currency), "giu"), "")
    .replace(/[₽$€£¥]/gu, "")
    .trim();
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function mappingWarningMessage(
  warning: ImportMappingPreviewDto["warnings"][number],
): string {
  if (warning.code === "unsigned_amount_direction_required") {
    return warning.affectedRowCount != null
      ? `${inRows(warning.affectedRowCount)} сумма указана без знака. Выберите, считать такие суммы поступлением или списанием.`
      : "В выписке есть суммы без знака. Выберите, считать такие суммы поступлением или списанием.";
  }
  return (
    {
      high_error_rate:
        "Много строк не удалось нормализовать. Проверьте первую строку и выбранные роли.",
      no_valid_rows:
        "Не найдено ни одной корректной строки. Измените настройку колонок.",
      balance_after_parse_errors:
        "Часть значений остатка не распознана и потребует проверки.",
    }[warning.code] ?? "Проверьте результат распознавания перед продолжением."
  );
}

function previewStatus(
  preview: ImportMappingPreviewDto,
  stale: boolean,
): { label: string; tone: "success" | "warning" | "danger" } {
  if (stale) return { label: "Нужно обновить", tone: "warning" };
  if (preview.reconciliation && !preview.reconciliation.matches) {
    return { label: "Остатки не сошлись", tone: "warning" };
  }
  if (preview.invalidRowCount > 0) {
    if (!preview.canImport) {
      return { label: "Продолжить нельзя", tone: "danger" };
    }
    return {
      label: rowsRequireFix(preview.invalidRowCount),
      tone: preview.warnings.some(
        (warning) => warning.code === "high_error_rate",
      )
        ? "danger"
        : "warning",
    };
  }
  return preview.canImport
    ? { label: "Все строки распознаны", tone: "success" }
    : { label: "Нужно исправить", tone: "danger" };
}

function rowsRequireFix(count: number): string {
  const lastTwoDigits = count % 100;
  const lastDigit = lastTwoDigits % 10;
  const noun =
    lastTwoDigits >= 11 && lastTwoDigits <= 14
      ? "строк"
      : lastDigit === 1
        ? "строка"
        : lastDigit >= 2 && lastDigit <= 4
          ? "строки"
          : "строк";
  const verb = lastTwoDigits !== 11 && lastDigit === 1 ? "требует" : "требуют";
  return `${count} ${noun} ${verb} исправления`;
}

function inRows(count: number): string {
  const lastTwoDigits = count % 100;
  const lastDigit = lastTwoDigits % 10;
  const noun =
    lastTwoDigits >= 11 && lastTwoDigits <= 14
      ? "строках"
      : lastDigit === 1
        ? "строке"
        : "строках";
  return `В ${count} ${noun}`;
}

function focusMappingField(fieldId: string) {
  const field = document.getElementById(fieldId);
  field?.scrollIntoView?.({ block: "center" });
  field?.focus();
}

function mappingRowErrorMessage(code: string): string {
  return (
    {
      operation_date_required: "В строке нет даты операции.",
      operation_date_invalid: "Дата операции не распознана.",
      posting_date_invalid: "Дата проводки не распознана.",
      amount_required: "В строке нет суммы.",
      amount_invalid: "Сумма не распознана.",
      unsigned_amount_direction_required:
        "У суммы нет знака. Выберите, считать её поступлением или списанием.",
      debit_invalid: "Списание не распознано.",
      credit_invalid: "Зачисление не распознано.",
      debit_and_credit_present: "Одновременно заполнены списание и зачисление.",
      balance_after_invalid: "Остаток после операции не распознан.",
      description_required: "В строке нет описания.",
    }[code] ?? "Строка требует ручной проверки."
  );
}
