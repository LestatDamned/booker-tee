import { useRef, useState, type FormEvent } from "react";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { Button } from "../../ui/button/button";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../../ui/field/form-error-summary";
import { Icon } from "../../ui/icon/icon";
import {
  StatusLabel,
  type StatusTone,
} from "../../ui/status-label/status-label";
import type {
  ImportMappingCommand,
  ImportMappingDto,
  ImportMappingPreviewDto,
} from "./api/import-mapping-api";
import { previewImportMapping } from "./api/import-mapping-api";
import styles from "./import-mapping-page.module.css";
import {
  mappingFingerprint,
  mappingForTable,
  mappingTableKey,
  validateMappingDraft,
  type MappingFieldErrors,
} from "./mapping-draft";
import { MappingForm } from "./mapping-form";
import { MappingPreview } from "./mapping-preview";

type PreviewSnapshot = {
  fingerprint: string;
  preview: ImportMappingPreviewDto;
};

export function ImportMappingPage({
  mapping,
  session,
}: {
  mapping: ImportMappingDto;
  session: SessionDto;
}) {
  const firstTable =
    mapping.tables.find(
      (table) =>
        mappingTableKey(table.ref) ===
        mappingTableKey(mapping.defaultMapping.tableRef),
    ) ?? mapping.tables[0];
  const initialCommand = firstTable
    ? mappingForTable(firstTable, mapping.defaultMapping)
    : mapping.defaultMapping;
  const initialTableKey = firstTable
    ? mappingTableKey(firstTable.ref)
    : mappingTableKey(mapping.defaultMapping.tableRef);
  const [activeTableKey, setActiveTableKey] = useState(initialTableKey);
  const [draftsByTable, setDraftsByTable] = useState<
    Record<string, ImportMappingCommand>
  >({ [initialTableKey]: initialCommand });
  const [fieldErrors, setFieldErrors] = useState<MappingFieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [previewSnapshot, setPreviewSnapshot] =
    useState<PreviewSnapshot | null>(null);
  const [pending, setPending] = useState(false);
  const previewHeadingRef = useRef<HTMLHeadingElement>(null);

  const activeTable = mapping.tables.find(
    (table) => mappingTableKey(table.ref) === activeTableKey,
  );
  const command =
    draftsByTable[activeTableKey] ??
    (activeTable
      ? mappingForTable(activeTable, mapping.defaultMapping)
      : mapping.defaultMapping);
  const currentFingerprint = mappingFingerprint(command);
  const previewStale =
    previewSnapshot !== null &&
    previewSnapshot.fingerprint !== currentFingerprint;
  const previewFieldErrors =
    previewSnapshot && !previewStale
      ? mappingPreviewFieldErrors(previewSnapshot.preview)
      : {};

  const updateCommand = (nextCommand: ImportMappingCommand) => {
    setDraftsByTable((current) => ({
      ...current,
      [activeTableKey]: nextCommand,
    }));
    setFieldErrors({});
    setSubmitError(null);
  };

  const selectTable = (nextTableKey: string) => {
    const nextTable = mapping.tables.find(
      (table) => mappingTableKey(table.ref) === nextTableKey,
    );
    if (!nextTable) return;
    setDraftsByTable((current) => ({
      ...current,
      [nextTableKey]:
        current[nextTableKey] ??
        mappingForTable(nextTable, mapping.defaultMapping),
    }));
    setActiveTableKey(nextTableKey);
    setFieldErrors({});
    setSubmitError(null);
  };

  const runPreview = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (!activeTable || pending) return;
    const clientErrors = validateMappingDraft(command, activeTable);
    setFieldErrors(clientErrors);
    setSubmitError(null);
    const firstError = firstMappingError(clientErrors);
    if (firstError) {
      focusMappingField(firstError);
      return;
    }

    setPending(true);
    const result = await previewImportMapping({
      command,
      csrfToken: session.csrfToken,
      documentId: mapping.documentId,
    });
    setPending(false);
    if (result.status === "unauthenticated") {
      window.location.assign(
        `/login?next=${encodeURIComponent(window.location.pathname)}`,
      );
      return;
    }
    if (result.status === "validation_error") {
      const errors = Object.fromEntries(
        Object.entries(result.fieldErrors).map(([field, messages]) => [
          field,
          messages[0] ?? result.message,
        ]),
      );
      setFieldErrors(errors);
      setSubmitError(result.message);
      const field = firstMappingError(errors);
      if (field) focusMappingField(field);
      return;
    }
    if (result.status !== "success") {
      setSubmitError(result.message);
      return;
    }
    setFieldErrors({});
    setSubmitError(null);
    setPreviewSnapshot({
      fingerprint: currentFingerprint,
      preview: result.preview,
    });
    requestAnimationFrame(() => previewHeadingRef.current?.focus());
  };

  const summaryErrors = mappingErrorSummary(fieldErrors);
  const status = documentStatus(mapping.status);

  return (
    <AppShell session={session}>
      <main className={styles.page}>
        <a
          className={styles.backLink}
          href={`/app/imports/documents/${mapping.documentId}`}
        >
          ← К документу
        </a>

        <section className={styles.workbench}>
          <header className={styles.workbenchHeader}>
            <div className={styles.identity}>
              <p className={styles.eyebrow}>Настройка импорта</p>
              <h1>{mapping.account?.name ?? "Счёт не определён"}</h1>
              <p className={styles.documentContext}>
                {[mapping.bankName, mapping.defaultCurrency]
                  .filter(Boolean)
                  .join(" · ") || "Реквизиты выписки не определены"}
              </p>
              <p className={styles.filename} title={mapping.filename}>
                {mapping.filename}
              </p>
            </div>
            <div className={styles.headerStatus}>
              <span>Состояние документа</span>
              <StatusLabel tone={status.tone} variant="soft">
                {status.label}
              </StatusLabel>
            </div>
          </header>

          <div className={styles.phoneNotice}>
            <Icon name="information" size={20} />
            <p>
              Сопоставлять колонки удобнее на экране компьютера. Здесь доступен
              тот же полный интерфейс с прокруткой таблицы.
            </p>
          </div>

          {!mapping.capability.allowed ? (
            <MappingUnavailable mapping={mapping} />
          ) : !activeTable ? (
            <section className={styles.unavailable} role="status">
              <Icon name="source" size={28} />
              <div>
                <h2>Таблицы не найдены</h2>
                <p>
                  Из документа не удалось получить источник для настройки
                  колонок. Исходный файл и результат парсинга сохранены.
                </p>
              </div>
            </section>
          ) : (
            <>
              <div className={styles.mappingWorkspace}>
                {(submitError || summaryErrors.length > 0) && (
                  <FormErrorSummary
                    errors={summaryErrors}
                    headingLevel={3}
                    message={
                      submitError ??
                      "Исправьте роли колонок и повторите предпросмотр."
                    }
                  />
                )}
                <MappingForm
                  command={command}
                  disabled={pending}
                  errors={{ ...previewFieldErrors, ...fieldErrors }}
                  table={activeTable}
                  tables={mapping.tables}
                  onChange={updateCommand}
                  onSelectTable={selectTable}
                  onSubmit={runPreview}
                />
                <MappingPreview
                  headingRef={previewHeadingRef}
                  preview={previewSnapshot?.preview ?? null}
                  stale={previewStale}
                />
              </div>

              <footer className={styles.actionBar}>
                <div aria-live="polite">
                  <strong>{actionStatus(previewSnapshot, previewStale)}</strong>
                  <span>
                    Предпросмотр ничего не записывает в официальный учёт.
                  </span>
                </div>
                <Button
                  form="mapping-form"
                  icon="check"
                  isLoading={pending}
                  tone="primary"
                  type="submit"
                >
                  {pending
                    ? "Проверяем строки…"
                    : previewSnapshot
                      ? "Обновить предпросмотр"
                      : "Показать предпросмотр"}
                </Button>
              </footer>
            </>
          )}
        </section>
      </main>
    </AppShell>
  );
}

function MappingUnavailable({ mapping }: { mapping: ImportMappingDto }) {
  const reason = mapping.capability.blockingReasonCodes[0];
  const content = {
    account_required: {
      title: "Не выбран счёт выписки",
      message:
        "Для создания строк нужен счёт и валюта, к которым относится документ.",
    },
    raw_tables_unavailable: {
      title: "Исходные таблицы недоступны",
      message:
        "Парсер не сохранил таблицы для сопоставления. Исходный документ остаётся доступен.",
    },
    mapping_not_required: {
      title: "Настройка больше не требуется",
      message:
        "Состояние документа изменилось: откройте его карточку, чтобы увидеть актуальный следующий шаг.",
    },
    confirmed_rows_exist: {
      title: "Строки уже проведены",
      message:
        "Документ связан с подтверждённым учётом, поэтому менять схему импорта небезопасно.",
    },
  }[reason ?? "mapping_not_required"];
  return (
    <section className={styles.unavailable} role="status">
      <Icon name="information" size={28} />
      <div>
        <h2>{content.title}</h2>
        <p>{content.message}</p>
        <a href={`/app/imports/documents/${mapping.documentId}`}>
          Открыть документ
        </a>
      </div>
    </section>
  );
}

function mappingErrorSummary(
  errors: MappingFieldErrors,
): FormErrorSummaryItem[] {
  const labels: Record<string, string> = {
    tableRef: "Исходная таблица",
    operationDateColumn: "Дата операции",
    postingDateColumn: "Дата проводки",
    descriptionColumn: "Описание",
    amountColumn: "Сумма",
    debitAmountColumn: "Списание",
    creditAmountColumn: "Зачисление",
    currencyColumn: "Валюта из строки",
    balanceAfterColumn: "Остаток",
    firstDataRowNumber: "С какой строки начинаются операции",
    defaultCurrency: "Валюта, если она не указана",
    unsignedAmountDirection: "Если у суммы нет знака",
  };
  return Object.entries(errors).map(([field, message]) => ({
    fieldId: mappingColumnFieldNames.has(field) ? "mapping-roles" : field,
    label: labels[field] ?? "Настройка",
    message,
  }));
}

const mappingColumnFieldNames = new Set([
  "operationDateColumn",
  "postingDateColumn",
  "descriptionColumn",
  "amountColumn",
  "debitAmountColumn",
  "creditAmountColumn",
  "currencyColumn",
  "balanceAfterColumn",
]);

function focusMappingField(field: string) {
  const target =
    document.getElementById(field) ??
    (mappingColumnFieldNames.has(field)
      ? document.querySelector<HTMLElement>("[data-mapping-role-select]")
      : null);
  target?.focus();
}

function firstMappingError(errors: MappingFieldErrors): string | null {
  const order = [
    "operationDateColumn",
    "descriptionColumn",
    "amountColumn",
    "unsignedAmountDirection",
    "debitAmountColumn",
    "creditAmountColumn",
    "firstDataRowNumber",
    "postingDateColumn",
    "currencyColumn",
    "balanceAfterColumn",
    "defaultCurrency",
  ];
  return order.find((field) => errors[field]) ?? null;
}

function actionStatus(
  snapshot: PreviewSnapshot | null,
  stale: boolean,
): string {
  if (!snapshot) return "Предпросмотр ещё не выполнен";
  if (stale) return "Настройка изменилась";
  return `${snapshot.preview.validRowCount} из ${snapshot.preview.totalRowCount} строк корректны`;
}

function mappingPreviewFieldErrors(
  preview: ImportMappingPreviewDto,
): MappingFieldErrors {
  const unsignedAmountWarning = preview.warnings.find(
    (warning) =>
      warning.code === "unsigned_amount_direction_required" &&
      warning.fields.includes("unsignedAmountDirection"),
  );
  if (!unsignedAmountWarning) return {};
  const count = unsignedAmountWarning.affectedRowCount;
  return {
    unsignedAmountDirection:
      count != null
        ? `${inRows(count)} сумма указана без знака. Выберите поступление или списание.`
        : "В выписке есть суммы без знака. Выберите поступление или списание.",
  };
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

function documentStatus(status: ImportMappingDto["status"]): {
  label: string;
  tone: StatusTone;
} {
  const values: Record<
    ImportMappingDto["status"],
    { label: string; tone: StatusTone }
  > = {
    uploaded: { label: "Загружен", tone: "neutral" },
    pending_parse: { label: "Ожидает обработки", tone: "neutral" },
    parsing: { label: "Обрабатывается", tone: "information" },
    parsed: { label: "Распознан", tone: "information" },
    requires_review: { label: "Требует настройки", tone: "warning" },
    failed_to_parse: { label: "Ошибка обработки", tone: "danger" },
    imported: { label: "Импортирован", tone: "success" },
    ignored: { label: "Игнорируется", tone: "neutral" },
  };
  return values[status];
}
