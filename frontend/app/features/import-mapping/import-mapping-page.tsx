import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

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
import {
  commitImportMapping,
  previewImportMapping,
} from "./api/import-mapping-api";
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
  const navigate = useNavigate();
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
  const [previewPending, setPreviewPending] = useState(false);
  const [importPending, setImportPending] = useState(false);
  const [saveTemplate, setSaveTemplate] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [templateError, setTemplateError] = useState<string | null>(null);
  const previewHeadingRef = useRef<HTMLHeadingElement>(null);
  const importAttemptRef = useRef<{
    fingerprint: string;
    idempotencyKey: string;
  } | null>(null);

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
  const canImport =
    previewSnapshot !== null &&
    !previewStale &&
    previewSnapshot.preview.canImport;
  const busy = previewPending || importPending;

  const updateCommand = (nextCommand: ImportMappingCommand) => {
    const controlTotalsChanged =
      JSON.stringify(nextCommand.openingBalanceCell ?? null) !==
        JSON.stringify(command.openingBalanceCell ?? null) ||
      JSON.stringify(nextCommand.closingBalanceCell ?? null) !==
        JSON.stringify(command.closingBalanceCell ?? null);
    setDraftsByTable((current) => {
      const nextDrafts = {
        ...current,
        [activeTableKey]: nextCommand,
      };
      if (!controlTotalsChanged) return nextDrafts;
      return Object.fromEntries(
        Object.entries(nextDrafts).map(([key, draft]) => [
          key,
          {
            ...draft,
            openingBalanceCell: nextCommand.openingBalanceCell ?? null,
            closingBalanceCell: nextCommand.closingBalanceCell ?? null,
          },
        ]),
      );
    });
    setFieldErrors({});
    setSubmitError(null);
    importAttemptRef.current = null;
  };

  const selectTable = (nextTableKey: string) => {
    const nextTable = mapping.tables.find(
      (table) => mappingTableKey(table.ref) === nextTableKey,
    );
    if (!nextTable) return;
    setDraftsByTable((current) => ({
      ...current,
      [nextTableKey]:
        current[nextTableKey] ?? mappingForTable(nextTable, command),
    }));
    setActiveTableKey(nextTableKey);
    setFieldErrors({});
    setSubmitError(null);
    importAttemptRef.current = null;
  };

  const runPreview = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (!activeTable || busy) return;
    const clientErrors = validateMappingDraft(command, activeTable);
    setFieldErrors(clientErrors);
    setSubmitError(null);
    const firstError = firstMappingError(clientErrors);
    if (firstError) {
      focusMappingField(firstError);
      return;
    }

    setPreviewPending(true);
    const result = await previewImportMapping({
      command,
      csrfToken: session.csrfToken,
      documentId: mapping.documentId,
    });
    setPreviewPending(false);
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

  const runImport = async () => {
    if (!canImport || !previewSnapshot || busy) return;
    const cleanedTemplateName = saveTemplate ? templateName.trim() : null;
    if (saveTemplate && !cleanedTemplateName) {
      setTemplateError("Введите понятное название шаблона.");
      document.getElementById("mappingTemplateName")?.focus();
      return;
    }

    setTemplateError(null);
    setSubmitError(null);
    const fingerprint = JSON.stringify([
      currentFingerprint,
      cleanedTemplateName,
    ]);
    const attempt =
      importAttemptRef.current?.fingerprint === fingerprint
        ? importAttemptRef.current
        : {
            fingerprint,
            idempotencyKey: crypto.randomUUID(),
          };
    importAttemptRef.current = attempt;
    setImportPending(true);
    const result = await commitImportMapping({
      command,
      csrfToken: session.csrfToken,
      documentId: mapping.documentId,
      idempotencyKey: attempt.idempotencyKey,
      templateName: cleanedTemplateName,
    });
    setImportPending(false);

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
    void navigate(
      `/imports/documents/${result.result.reviewTarget.documentId}/review`,
    );
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
                  disabled={busy}
                  errors={{ ...previewFieldErrors, ...fieldErrors }}
                  mapping={mapping}
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
                {canImport ? (
                  <section
                    aria-labelledby="mapping-template-title"
                    className={styles.importOptions}
                  >
                    <div>
                      <p className={styles.sectionLabel}>Необязательно</p>
                      <h2 id="mapping-template-title">
                        Сохранить настройку колонок
                      </h2>
                      <p>
                        Шаблон пригодится для следующих выписок с такой же
                        структурой.
                      </p>
                    </div>
                    <label className={styles.templateToggle}>
                      <input
                        checked={saveTemplate}
                        disabled={busy}
                        onChange={(event) => {
                          setSaveTemplate(event.target.checked);
                          setTemplateError(null);
                          importAttemptRef.current = null;
                        }}
                        type="checkbox"
                      />
                      <span>Сохранить как шаблон</span>
                    </label>
                    {saveTemplate ? (
                      <div className={styles.templateName}>
                        <label htmlFor="mappingTemplateName">
                          Название шаблона *
                        </label>
                        <input
                          aria-describedby={
                            templateError
                              ? "mappingTemplateName-error"
                              : undefined
                          }
                          aria-invalid={templateError ? "true" : undefined}
                          disabled={busy}
                          id="mappingTemplateName"
                          maxLength={255}
                          onChange={(event) => {
                            setTemplateName(event.target.value);
                            setTemplateError(null);
                            importAttemptRef.current = null;
                          }}
                          placeholder="Например, Экспобанк — карта"
                          value={templateName}
                        />
                        {templateError ? (
                          <span
                            className={styles.templateError}
                            id="mappingTemplateName-error"
                          >
                            {templateError}
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                  </section>
                ) : null}
              </div>

              <footer className={styles.actionBar}>
                <div aria-live="polite">
                  <strong>{actionStatus(previewSnapshot, previewStale)}</strong>
                  <span>
                    Предпросмотр ничего не записывает в официальный учёт.
                  </span>
                </div>
                <div className={styles.actionButtons}>
                  {canImport ? (
                    <Button
                      disabled={busy}
                      form="mapping-form"
                      tone="secondary"
                      type="submit"
                    >
                      Обновить предпросмотр
                    </Button>
                  ) : null}
                  <Button
                    form={canImport ? undefined : "mapping-form"}
                    icon="check"
                    isLoading={busy}
                    onClick={canImport ? runImport : undefined}
                    tone="primary"
                    type={canImport ? "button" : "submit"}
                  >
                    {importPending
                      ? "Создаём строки…"
                      : previewPending
                        ? "Проверяем строки…"
                        : canImport
                          ? `Импортировать ${previewSnapshot.preview.totalRowCount} строк`
                          : previewSnapshot
                            ? "Обновить предпросмотр"
                            : "Показать предпросмотр"}
                  </Button>
                </div>
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
  if (
    snapshot.preview.reconciliation &&
    !snapshot.preview.reconciliation.matches
  ) {
    return "Строки распознаны, но остатки не сошлись";
  }
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
