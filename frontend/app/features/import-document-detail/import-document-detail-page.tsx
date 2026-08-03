import { useState } from "react";
import { useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { AppShell } from "../../shell/app-shell";
import { BackLink } from "../../ui/back-link/back-link";
import { Button, ButtonLink } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { DocumentWorkbenchHeader } from "../../ui/document-workbench-header/document-workbench-header";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { MoneyValue, type MoneyTone } from "../../ui/money-value/money-value";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { ReadOnlyFinancialRow } from "../../ui/read-only-financial-row/read-only-financial-row";
import {
  StatusLabel,
  type StatusTone,
} from "../../ui/status-label/status-label";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import {
  mutateImportDocument,
  type ImportDocumentDetailDto,
  type ImportDocumentManagementAction,
} from "./api/import-document-detail-api";
import styles from "./import-document-detail-page.module.css";

type Props = {
  initialDocument: ImportDocumentDetailDto;
  session: SessionDto;
};

const statusCopy: Record<
  ImportDocumentDetailDto["status"],
  { label: string; tone: StatusTone }
> = {
  uploaded: { label: "Загружен", tone: "information" },
  pending_parse: { label: "Ожидает обработки", tone: "information" },
  parsing: { label: "Обрабатывается", tone: "automation" },
  parsed: { label: "Готов к проверке", tone: "success" },
  requires_review: { label: "Требует действия", tone: "warning" },
  failed_to_parse: { label: "Ошибка обработки", tone: "danger" },
  imported: { label: "Импортирован", tone: "success" },
  ignored: { label: "Игнорируется", tone: "neutral" },
};

const workflowLabels = [
  ["upload", "Загрузка", "Файл"],
  ["extract", "Извлечение", "Данные"],
  ["mapping", "Настройка", "Колонки"],
  ["review", "Проверка", "Проверка"],
  ["ledger", "Учёт", "Учёт"],
] as const;

export function ImportDocumentDetailPage({ initialDocument, session }: Props) {
  const navigate = useNavigate();
  const [document, setDocument] = useState(initialDocument);
  const [pending, setPending] = useState<ImportDocumentManagementAction | null>(
    null,
  );
  const [confirmation, setConfirmation] =
    useState<ImportDocumentManagementAction | null>(null);
  const [feedback, setFeedback] = useState<{
    tone: "success" | "error";
    message: string;
  } | null>(null);
  const status = statusCopy[document.status];
  const nextStep = nextStepPresentation(document);

  async function run(action: ImportDocumentManagementAction) {
    setConfirmation(null);
    setPending(action);
    setFeedback(null);
    const result = await mutateImportDocument(
      document,
      action,
      session.csrfToken,
    );
    setPending(null);
    if (redirectIfUnauthenticated(result)) return;
    if (result.status !== "success") {
      setFeedback({ tone: "error", message: result.message });
      return;
    }
    if (action === "delete") {
      void navigate("/imports");
      return;
    }
    if (result.document) setDocument(result.document);
    setFeedback({
      tone: "success",
      message: "Документ отмечен как игнорируемый.",
    });
  }

  return (
    <AppShell session={session}>
      <PageFrame className={styles.page} spacing="none">
        <BackLink to="/imports">Все импорты</BackLink>

        <WorkbenchSurface
          aria-label="Документ импорта"
          className={styles.workbench}
        >
          <DocumentWorkbenchHeader
            context={
              documentIdentity(document) || "Реквизиты выписки не определены"
            }
            eyebrow="Импорт банковской выписки"
            filename={document.filename}
            status={
              <StatusLabel tone={status.tone} variant="soft">
                {status.label}
              </StatusLabel>
            }
            title={document.account?.name ?? "Счёт не определён"}
          />

          {feedback ? (
            <InlineNotice
              action={
                feedback.tone === "error" ? (
                  <Button
                    icon="retry"
                    onClick={() => window.location.reload()}
                    type="button"
                  >
                    Обновить страницу
                  </Button>
                ) : undefined
              }
              className={styles.documentFeedback}
              role={feedback.tone === "error" ? "alert" : "status"}
              tone={feedback.tone === "error" ? "danger" : "success"}
            >
              {feedback.message}
            </InlineNotice>
          ) : null}

          <section className={styles.decisionRegion} aria-label="Следующий шаг">
            <div className={styles.decisionBar}>
              <div className={styles.decisionMarker} aria-hidden="true" />
              <div>
                <span className={styles.sectionLabel}>Требуется сейчас</span>
                <h2>{nextStep.title}</h2>
                <p>{nextStep.description}</p>
              </div>
              <ButtonLink
                className={styles.primaryAction ?? ""}
                href={nextStep.href}
                tone="primary"
              >
                {nextStep.action}
              </ButtonLink>
            </div>

            <nav aria-label="Этапы импорта" className={styles.workflow}>
              <ol>
                {workflowLabels.map(([key, label, compactLabel]) => (
                  <li data-state={document.workflow[key]} key={key}>
                    <span aria-hidden="true" />
                    <div>
                      <strong>
                        <span className={styles.fullWorkflowLabel}>
                          {label}
                        </span>
                        <span className={styles.compactWorkflowLabel}>
                          {compactLabel}
                        </span>
                      </strong>
                      <small>
                        {workflowStateLabel(document.workflow[key])}
                      </small>
                    </div>
                  </li>
                ))}
              </ol>
            </nav>
          </section>

          <div className={styles.contentGrid}>
            <div className={styles.primaryColumn}>
              <ValidationSection document={document} />
              <RawRowsSection document={document} />
              <ParseHistorySection document={document} />
            </div>
            <aside className={styles.sideColumn}>
              <section className={styles.facts}>
                <h2>О выписке</h2>
                <dl>
                  <div>
                    <dt>Период</dt>
                    <dd>{statementPeriod(document)}</dd>
                  </div>
                  <div>
                    <dt>Загружена</dt>
                    <dd>{formatDateTime(document.createdAt)}</dd>
                  </div>
                </dl>
              </section>

              <ManagementSection
                document={document}
                onConfirm={setConfirmation}
              />
            </aside>
          </div>
        </WorkbenchSurface>

        {confirmation ? (
          <ConfirmationDialog
            confirmLabel={
              confirmation === "delete" ? "Удалить документ" : "Игнорировать"
            }
            description={confirmationDescription(confirmation)}
            onCancel={() => setConfirmation(null)}
            onConfirm={() => void run(confirmation)}
            pending={pending === confirmation}
            title={
              confirmation === "delete"
                ? "Удалить выписку?"
                : "Игнорировать выписку?"
            }
          />
        ) : null}
      </PageFrame>
    </AppShell>
  );
}

function ValidationSection({
  document,
}: {
  document: ImportDocumentDetailDto;
}) {
  const validation = document.validation;
  const presentation = validation ? validationPresentation(validation) : null;
  return (
    <section className={styles.validationSection}>
      <header className={styles.sectionHeader}>
        <div>
          <span className={styles.sectionLabel}>Контроль результата</span>
          <h2>Что удалось извлечь</h2>
        </div>
        {presentation ? (
          <StatusLabel tone={presentation.tone} variant="soft">
            {presentation.label}
          </StatusLabel>
        ) : null}
      </header>
      {validation ? (
        <>
          <div className={styles.metrics}>
            <Metric
              label="Строки"
              value={
                validation.extractedCount?.toLocaleString("ru-RU") ??
                document.rawRows.total.toLocaleString("ru-RU")
              }
            />
            <Metric
              label="Приход"
              value={money(
                validation.calculatedTotalInflow,
                validation.currency,
              )}
            />
            <Metric
              label="Расход"
              value={money(
                validation.calculatedTotalOutflow,
                validation.currency,
              )}
            />
            <Metric
              label={validation.needsMapping ? "Таблицы" : "Исключено"}
              value={
                validation.needsMapping
                  ? (validation.tableCount?.toLocaleString("ru-RU") ?? "—")
                  : validation.ignoredRowCount.toLocaleString("ru-RU")
              }
            />
          </div>
          <p className={styles.validationMessage}>
            {presentation?.description ??
              localizedValidationMessage(validation)}
          </p>
        </>
      ) : (
        <p className={styles.muted}>
          Контрольный отчёт пока недоступен. История обработки ниже покажет,
          запускался ли парсер и чем завершилась попытка.
        </p>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RawRowsSection({ document }: { document: ImportDocumentDetailDto }) {
  return (
    <section
      aria-labelledby="import-document-rows-title"
      className={styles.rowsSection}
    >
      <header className={styles.rowsHeader}>
        <div>
          <h2 id="import-document-rows-title">Пример извлечённых строк</h2>
          <p>
            Показано {document.rawRows.items.length} из {document.rawRows.total}
          </p>
        </div>
        {document.nextStep === "review" ? (
          <a href={`/app/imports/documents/${document.id}/review`}>
            Открыть проверку
          </a>
        ) : null}
      </header>
      {document.rawRows.items.length ? (
        <ol className={styles.rows}>
          {document.rawRows.items.map((row) => (
            <li key={row.rowIndex}>
              <ReadOnlyFinancialRow
                date={formatRowDate(row.displayDate)}
                dateTime={row.displayDate ?? undefined}
                description={row.description || "Без описания"}
                issues={
                  row.normalizationError ? (
                    <p role="alert">{row.normalizationError}</p>
                  ) : undefined
                }
                status={
                  <StatusLabel tone={rawStatusTone(row.status)} variant="plain">
                    {rawStatusLabel(row.status)}
                  </StatusLabel>
                }
                tone={row.normalizationError ? "problem" : "default"}
                value={
                  <MoneyValue
                    amount={formatSignedAmount(row.amount ?? row.amountRaw)}
                    currency={row.currency ?? ""}
                    tone={rawAmountTone(row.amount ?? row.amountRaw)}
                  />
                }
              />
            </li>
          ))}
        </ol>
      ) : (
        <p className={styles.muted}>{rawRowsEmptyMessage(document)}</p>
      )}
    </section>
  );
}

function ParseHistorySection({
  document,
}: {
  document: ImportDocumentDetailDto;
}) {
  return (
    <details
      className={styles.disclosure}
      open={document.status === "failed_to_parse"}
    >
      <summary>
        <span>
          <strong>История обработки</strong>
          <small>{document.parseAttempts.total} попыток</small>
        </span>
        <span aria-hidden="true">Раскрыть</span>
      </summary>
      <ol className={styles.attempts}>
        {document.parseAttempts.items.map((attempt) => (
          <li key={attempt.id}>
            <StatusLabel
              tone={attempt.status === "failed" ? "danger" : "neutral"}
            >
              {attemptStatusLabel(attempt.status)}
            </StatusLabel>
            <div>
              <strong>
                {attempt.parserName}
                {attempt.parserVersion ? ` ${attempt.parserVersion}` : ""}
              </strong>
              <span>{formatDateTime(attempt.startedAt)}</span>
              {attempt.message ? <p>{attempt.message}</p> : null}
            </div>
          </li>
        ))}
      </ol>
    </details>
  );
}

function ManagementSection({
  document,
  onConfirm,
}: {
  document: ImportDocumentDetailDto;
  onConfirm: (action: ImportDocumentManagementAction) => void;
}) {
  if (!document.capabilities.canManage) {
    return (
      <section className={styles.management}>
        <h2>Только просмотр</h2>
        <p>Ваша роль позволяет изучить результат, но не изменять документ.</p>
      </section>
    );
  }
  return (
    <section className={styles.management}>
      <header>
        <span className={styles.sectionLabel}>Документ</span>
        <h2>Управление документом</h2>
      </header>
      <div className={styles.managementActions}>
        <Button
          disabled={!document.capabilities.ignore.allowed}
          onClick={() => onConfirm("ignore")}
        >
          Игнорировать
        </Button>
        <div className={styles.dangerZone}>
          <Button
            disabled={!document.capabilities.delete.allowed}
            onClick={() => onConfirm("delete")}
            tone="dangerSecondary"
          >
            Удалить
          </Button>
        </div>
      </div>
      <CapabilityReasons document={document} />
    </section>
  );
}

function CapabilityReasons({
  document,
}: {
  document: ImportDocumentDetailDto;
}) {
  const reasons = new Set([
    ...document.capabilities.ignore.blockingReasonCodes,
    ...document.capabilities.delete.blockingReasonCodes,
  ]);
  if (!reasons.size) return null;
  return (
    <ul className={styles.reasons}>
      {[...reasons].map((reason) => (
        <li key={reason}>{blockingReasonLabel(reason)}</li>
      ))}
    </ul>
  );
}

function nextStepPresentation(document: ImportDocumentDetailDto) {
  if (document.status === "imported") {
    return {
      title: "Импорт завершён",
      description:
        "Строки обработаны и добавлены в учёт; исключённые операции сохранены в истории.",
      action: "Посмотреть результат",
      href: `/app/imports/documents/${document.id}/review`,
    };
  }
  if (document.status === "ignored") {
    return {
      title: "Выписка исключена из обработки",
      description:
        "Файл и история сохранены, но строки больше не участвуют в очереди проверки.",
      action: "К списку импортов",
      href: "/app/imports",
    };
  }
  const values = {
    mapping: {
      title: "Системе нужно понять структуру выписки",
      description:
        "Файл прочитан, но даты, описания и суммы ещё не сопоставлены с колонками.",
      action: "Настроить колонки",
      href: `/app/imports/documents/${document.id}/mapping`,
    },
    review: {
      title: "Строки готовы к вашей проверке",
      description:
        "Проверьте классификацию, переводы и возможные дубли до попадания в официальный учёт.",
      action: "Перейти к проверке",
      href: `/app/imports/documents/${document.id}/review`,
    },
    upload: {
      title: "Выписку не удалось обработать",
      description:
        "Исходный файл сохранён. Посмотрите причину ниже или загрузите другую версию выписки.",
      action: "Загрузить другую",
      href: "/app/imports/upload",
    },
    document_list: {
      title: "Обработка ещё не завершена",
      description:
        "Вернитесь к реестру: следующий доступный шаг появится после извлечения данных.",
      action: "К списку импортов",
      href: "/app/imports",
    },
  } as const;
  return values[document.nextStep];
}

function documentIdentity(document: ImportDocumentDetailDto) {
  return [
    document.bankName,
    statementPeriod(document),
    document.account?.currency,
  ]
    .filter((value) => value && value !== "Не определён")
    .join(" · ");
}

function statementPeriod(document: ImportDocumentDetailDto) {
  if (!document.statementPeriodStart || !document.statementPeriodEnd) {
    return "Не определён";
  }
  const start = new Date(`${document.statementPeriodStart}T00:00:00`);
  const end = new Date(`${document.statementPeriodEnd}T00:00:00`);
  return `${start.toLocaleDateString("ru-RU")} — ${end.toLocaleDateString("ru-RU")}`;
}

function formatDateTime(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "Не определена";
}

function formatRowDate(value: string | null) {
  if (!value) return "Без даты";
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T00:00:00`)
    : new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("ru-RU");
}

function money(value: string | null, currency: string | null) {
  if (!value) return "—";
  const number = Number(value.replace(",", "."));
  return Number.isFinite(number)
    ? new Intl.NumberFormat("ru-RU", {
        style: currency ? "currency" : "decimal",
        ...(currency ? { currency } : {}),
      }).format(number)
    : `${value}${currency ? ` ${currency}` : ""}`;
}

function workflowStateLabel(
  state: ImportDocumentDetailDto["workflow"]["upload"],
) {
  return {
    pending: "ожидает",
    current: "сейчас",
    done: "готово",
    skipped: "не требуется",
    blocked: "ошибка",
  }[state];
}

function validationPresentation(
  validation: NonNullable<ImportDocumentDetailDto["validation"]>,
): {
  label: string;
  description: string;
  tone: StatusTone;
} {
  if (validation.reasonCode === "totals_match") {
    return {
      label: "Сверка сошлась",
      description: "Суммы строк совпадают с контрольными итогами выписки.",
      tone: "success",
    };
  }
  if (validation.reasonCode === "ignored_rows_explain_mismatch") {
    return {
      label: "Разница объяснена",
      description: ignoredRowsValidationDescription(validation),
      tone: "success",
    };
  }
  if (validation.reasonCode === "needs_mapping") {
    return {
      label: "Нужна настройка",
      description: localizedValidationMessage(validation),
      tone: "warning",
    };
  }
  if (validation.reasonCode === "rows_need_review") {
    return {
      label: "Нужна проверка строк",
      description:
        "Контрольные итоги можно оценить после проверки строк с нераспознанными данными.",
      tone: "warning",
    };
  }
  if (validation.reasonCode === "control_totals_unavailable") {
    return {
      label: "Сверка недоступна",
      description:
        "Итоги выписки не распознаны, поэтому сравнить их с суммами строк пока нельзя.",
      tone: "neutral",
    };
  }
  if (validation.reasonCode === "balance_chain_mismatch") {
    return {
      label: "Не сходится остаток",
      description:
        "Остаток после одной или нескольких операций отличается от указанного в выписке.",
      tone: "warning",
    };
  }
  if (validation.reasonCode === "validation_failed") {
    return {
      label: "Ошибка проверки",
      description:
        "Контроль результата не завершён. Изучите историю обработки или запустите документ заново.",
      tone: "danger",
    };
  }
  return {
    label: "Есть необъяснённая разница",
    description:
      "Суммы строк не совпадают с итогами выписки, и исключённые операции не объясняют разницу полностью.",
    tone: "warning",
  };
}

function ignoredRowsValidationDescription(
  validation: NonNullable<ImportDocumentDetailDto["validation"]>,
) {
  const count = validation.ignoredRowCount;
  const remainder100 = count % 100;
  const remainder10 = count % 10;
  const subject =
    remainder10 === 1 && remainder100 !== 11
      ? `${count} исключённая строка полностью объясняет`
      : remainder10 >= 2 &&
          remainder10 <= 4 &&
          (remainder100 < 12 || remainder100 > 14)
        ? `${count} исключённые строки полностью объясняют`
        : `${count} исключённых строк полностью объясняют`;
  return `${subject} разницу. Необъяснённой разницы нет.`;
}

function localizedValidationMessage(
  validation: NonNullable<ImportDocumentDetailDto["validation"]>,
) {
  if (validation.needsMapping) {
    return validation.tableCount
      ? "Файл прочитан, и таблицы с операциями найдены. Настройте колонки даты, описания и суммы."
      : "Файл прочитан, но таблица операций не определена. Проверьте структуру выписки перед настройкой.";
  }
  const messageIsAscii = [...validation.message].every(
    (character) => (character.codePointAt(0) ?? 0) <= 127,
  );
  if (messageIsAscii) {
    return validation.status === "valid"
      ? "Извлечённые данные прошли контрольную проверку."
      : "Проверьте результат извлечения перед продолжением.";
  }
  return validation.message;
}

function rawStatusLabel(status: string) {
  return (
    {
      extracted: "извлечено",
      normalized: "нормализовано",
      suggested: "есть предложение",
      needs_review: "нужна проверка",
      matched: "связано",
      ignored: "игнорируется",
      duplicate: "дубликат",
      possible_duplicate: "возможный дубль",
      failed: "ошибка",
      confirmed: "подтверждено",
    }[status] ?? status
  );
}

function rawStatusTone(status: string): StatusTone {
  if (status === "confirmed" || status === "matched") return "success";
  if (
    status === "needs_review" ||
    status === "possible_duplicate" ||
    status === "suggested"
  ) {
    return "warning";
  }
  if (status === "failed") return "danger";
  if (status === "normalized") return "information";
  return "neutral";
}

function rawAmountTone(value: string | null): MoneyTone {
  const parsed = parseNumber(value);
  if (parsed === null || parsed === 0) return "neutral";
  return parsed > 0 ? "income" : "expense";
}

function formatSignedAmount(value: string | null) {
  const parsed = parseNumber(value);
  if (parsed === null) return value || "—";
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    signDisplay: "exceptZero",
  }).format(parsed);
}

function parseNumber(value: string | null) {
  if (!value) return null;
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function attemptStatusLabel(status: string) {
  return (
    {
      running: "В процессе",
      success: "Успешно",
      requires_review: "Нужна проверка",
      failed: "Ошибка",
    }[status] ?? status
  );
}

function rawRowsEmptyMessage(document: ImportDocumentDetailDto) {
  if (document.validation?.needsMapping) {
    return "Строки появятся после настройки колонок.";
  }
  if (document.status === "failed_to_parse") {
    return "Из этой версии файла строки не извлечены.";
  }
  return "Строк пока нет.";
}

function blockingReasonLabel(reason: string) {
  return (
    {
      linked_operations_exist:
        "Игнорирование и удаление недоступны: документ связан с операциями.",
      already_ignored: "Документ уже игнорируется.",
      import_management_forbidden:
        "Недостаточно прав для управления импортами.",
    }[reason] ?? reason
  );
}

function confirmationDescription(action: ImportDocumentManagementAction) {
  return action === "delete"
    ? "Файл, попытки обработки и неподтверждённые строки будут удалены без возможности восстановления."
    : "Строки документа перестанут участвовать в очереди проверки. Сам файл и история сохранятся.";
}
