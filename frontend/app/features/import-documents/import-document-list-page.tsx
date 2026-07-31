import { useState } from "react";
import { useLocation } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { AppliedFilterSummary } from "../../ui/applied-filter-summary/applied-filter-summary";
import { Badge } from "../../ui/badge/badge";
import { Button, ButtonLink, RouterButtonLink } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import {
  StatusLabel,
  type StatusTone,
} from "../../ui/status-label/status-label";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchFilterRegion } from "../../ui/workbench-content/workbench-filter-region";
import { WorkbenchStatus } from "../../ui/workbench-content/workbench-status";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type {
  ImportDocumentListDto,
  ImportDocumentListItemDto,
} from "./api/import-documents-api";
import {
  importDocumentAppliedFilters,
  importDocumentFiltersAreActive,
  importDocumentStateUrl,
} from "./import-document-filter-query";
import { ImportDocumentFilters } from "./import-document-filters";
import { ImportDocumentPagination } from "./import-document-pagination";
import styles from "./import-document-list-page.module.css";

type ImportDocumentListPageProps = {
  documents: ImportDocumentListDto;
  navigationPending?: boolean;
  session: SessionDto;
};

const statusPresentation: Record<
  ImportDocumentListItemDto["status"],
  { label: string; tone: StatusTone }
> = {
  uploaded: { label: "Загружен", tone: "information" },
  pending_parse: { label: "Ожидает обработки", tone: "information" },
  parsing: { label: "Обрабатывается", tone: "automation" },
  parsed: { label: "Обработан", tone: "success" },
  requires_review: { label: "Требует внимания", tone: "warning" },
  failed_to_parse: { label: "Ошибка обработки", tone: "danger" },
  imported: { label: "Импортирован", tone: "success" },
  ignored: { label: "Игнорируется", tone: "neutral" },
};

const stateFilters = [
  { label: "Все", value: null },
  { label: "Требуют действия", value: "attention" },
  { label: "В обработке", value: "processing" },
  { label: "Завершены", value: "completed" },
] as const;
const knownStates = new Set<string>(
  stateFilters.flatMap((filter) =>
    filter.value === null ? [] : [filter.value],
  ),
);

export function ImportDocumentListPage({
  documents,
  navigationPending = false,
  session,
}: ImportDocumentListPageProps) {
  const location = useLocation();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const filtersActive = importDocumentFiltersAreActive(location.search);
  const appliedFilters = importDocumentAppliedFilters(
    location.search,
    documents.filterOptions,
  );
  const requestedState = new URLSearchParams(location.search).get("state");
  const activeState =
    requestedState !== null && knownStates.has(requestedState)
      ? requestedState
      : null;

  return (
    <AppShell session={session}>
      <PageFrame className={styles.page} spacing="none">
        <PageHeader
          actions={
            documents.capabilities.canUpload ? (
              <ButtonLink href="/app/imports/upload" tone="primary">
                Загрузить выписку
              </ButtonLink>
            ) : undefined
          }
          description="Выписки по счетам и их путь до проверенных операций."
          eyebrow={`${documents.workspaceName} · ${documentSummaryLabel(documents)}`}
          title="Импорты"
        />

        {!documents.capabilities.canUpload ? (
          <InlineNotice title="Режим только для чтения" tone="information">
            Документы доступны для просмотра, но загрузка и настройка импорта
            недоступны для вашей роли.
          </InlineNotice>
        ) : null}

        {documents.summary.totalDocumentCount === 0 ? (
          <WorkbenchEmptyState
            action={
              documents.capabilities.canUpload ? (
                <ButtonLink
                  href="/app/imports/upload"
                  icon="imports"
                  tone="primary"
                >
                  Загрузить первую выписку
                </ButtonLink>
              ) : undefined
            }
            icon="imports"
            title="Документов пока нет"
          >
            Загрузите первую выписку, чтобы подготовить операции к проверке.
          </WorkbenchEmptyState>
        ) : (
          <WorkbenchSurface
            aria-busy={navigationPending}
            aria-label="Реестр выписок"
            className={styles.registry}
          >
            <WorkbenchToolbar className={styles.registryToolbar}>
              <div className={styles.toolbarRow}>
                <SelectionTabs as="nav" aria-label="Состояние документов">
                  {stateFilters.map((filter) => {
                    const active =
                      activeState === filter.value ||
                      (filter.value === null && activeState === null);
                    const count =
                      filter.value === null
                        ? documents.summary.totalDocumentCount
                        : filter.value === "attention"
                          ? documents.summary.attentionDocumentCount
                          : undefined;
                    return (
                      <SelectionTabLink
                        {...(count === undefined ? {} : { count })}
                        key={filter.label}
                        selected={active}
                        to={importDocumentStateUrl(
                          location.search,
                          filter.value,
                        )}
                      >
                        {filter.label}
                      </SelectionTabLink>
                    );
                  })}
                </SelectionTabs>
                <Button
                  aria-controls="import-filter-region"
                  aria-expanded={filtersOpen}
                  disabled={navigationPending}
                  icon="filter"
                  onClick={() => setFiltersOpen((current) => !current)}
                >
                  Фильтры
                  {appliedFilters.length > 0 ? (
                    <Badge>{appliedFilters.length}</Badge>
                  ) : null}
                </Button>
              </div>
              <AppliedFilterSummary
                filters={filtersOpen ? [] : appliedFilters}
                resetTo={location.pathname}
              />
            </WorkbenchToolbar>

            {filtersOpen ? (
              <WorkbenchFilterRegion id="import-filter-region">
                <ImportDocumentFilters
                  key={location.search}
                  navigationPending={navigationPending}
                  onClose={() => setFiltersOpen(false)}
                  options={documents.filterOptions}
                />
              </WorkbenchFilterRegion>
            ) : null}

            <WorkbenchStatus>
              {navigationPending ? "Обновляем документы…" : ""}
            </WorkbenchStatus>

            <WorkbenchContent
              aria-label="Документы импорта"
              isEmpty={documents.items.length === 0}
            >
              {documents.items.length === 0 ? (
                <WorkbenchEmptyState
                  action={
                    filtersActive ? (
                      <RouterButtonLink icon="filter" to={location.pathname}>
                        Сбросить фильтры
                      </RouterButtonLink>
                    ) : undefined
                  }
                  icon="search"
                  kind="filtered"
                  title="По этим фильтрам документов нет"
                >
                  Измените условия или вернитесь ко всем документам.
                </WorkbenchEmptyState>
              ) : (
                <ResponsiveRecordCollection
                  mobileList={
                    <DocumentMobileList documents={documents.items} />
                  }
                  table={<DocumentTable documents={documents.items} />}
                />
              )}
            </WorkbenchContent>

            <ImportDocumentPagination
              disabled={navigationPending}
              documents={documents}
            />
          </WorkbenchSurface>
        )}
      </PageFrame>
    </AppShell>
  );
}

function DocumentTable({
  documents,
}: {
  documents: ImportDocumentListItemDto[];
}) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">
        Выписки, загруженные в текущий workspace
      </caption>
      <thead>
        <tr>
          <th scope="col">Выписка</th>
          <th scope="col">Период</th>
          <th scope="col">Загружена</th>
          <th scope="col">Статус</th>
          <th scope="col">Строки</th>
          <th scope="col">
            <span className="visually-hidden">Действие</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {documents.map((document) => (
          <DocumentTableRow document={document} key={document.id} />
        ))}
      </tbody>
    </table>
  );
}

function DocumentTableRow({
  document,
}: {
  document: ImportDocumentListItemDto;
}) {
  const status = statusPresentation[document.status];
  const action = documentAction(document);
  return (
    <tr>
      <th scope="row">
        <a data-record-identity href={`/app/imports/documents/${document.id}`}>
          {document.account?.name ?? "Счёт не определён"}
        </a>
        <span className={styles.bankName}>{documentBankName(document)}</span>
        <span className={styles.filename} title={document.filename}>
          {document.filename}
        </span>
      </th>
      <td>{formatStatementPeriod(document.statementPeriod)}</td>
      <td>
        <time dateTime={document.createdAt}>
          {formatUploadedDate(document.createdAt)}
        </time>
      </td>
      <td>
        <StatusLabel tone={status.tone} variant="soft">
          {status.label}
        </StatusLabel>
      </td>
      <td>
        <DocumentRowCount document={document} />
      </td>
      <td className={styles.actionCell}>
        <ButtonLink href={action.href}>{action.label}</ButtonLink>
      </td>
    </tr>
  );
}

function DocumentMobileList({
  documents,
}: {
  documents: ImportDocumentListItemDto[];
}) {
  return (
    <ol aria-label="Документы импорта">
      {documents.map((document) => {
        const status = statusPresentation[document.status];
        const action = documentAction(document);
        return (
          <li key={document.id}>
            <article className={styles.mobileRecord} data-responsive-record>
              <div className={styles.mobileHeading}>
                <div>
                  <a
                    data-record-identity
                    href={`/app/imports/documents/${document.id}`}
                  >
                    {document.account?.name ?? "Счёт не определён"}
                  </a>
                  <span className={styles.bankName}>
                    {documentBankName(document)}
                  </span>
                </div>
                <StatusLabel tone={status.tone} variant="soft">
                  {status.label}
                </StatusLabel>
              </div>
              <p className={styles.mobileFacts}>
                <span>{formatStatementPeriod(document.statementPeriod)}</span>
                <span>{formatUploadedDate(document.createdAt)}</span>
                <DocumentRowCount document={document} />
              </p>
              <span className={styles.filename} title={document.filename}>
                {document.filename}
              </span>
              <div className={styles.mobileAction}>
                <ButtonLink href={action.href}>{action.label}</ButtonLink>
              </div>
            </article>
          </li>
        );
      })}
    </ol>
  );
}

function DocumentRowCount({
  document,
}: {
  document: ImportDocumentListItemDto;
}) {
  if (document.reviewableRowCount > 0) {
    return (
      <span className={styles.rowCount}>
        {document.totalRowCount} ·{" "}
        <strong>{document.reviewableRowCount} ждут</strong>
      </span>
    );
  }
  return <span className={styles.rowCount}>{document.totalRowCount}</span>;
}

export function documentAction(document: ImportDocumentListItemDto): {
  href: string;
  label: string;
} {
  if (document.nextStepKind === "mapping" && document.capabilities.canMap) {
    return {
      href: `/app/imports/documents/${document.id}/mapping`,
      label: "Настроить",
    };
  }
  if (document.nextStepKind === "review" && document.capabilities.canReview) {
    return {
      href: `/app/imports/documents/${document.id}/review`,
      label: "Проверить",
    };
  }
  return {
    href: `/app/imports/documents/${document.id}`,
    label: "Открыть",
  };
}

export function formatStatementPeriod(
  period: ImportDocumentListItemDto["statementPeriod"],
): string {
  if (period === null) {
    return "Не определён";
  }
  const start = isoDateParts(period.start);
  const end = isoDateParts(period.end);
  if (
    start.year === end.year &&
    start.month === end.month &&
    start.day === 1 &&
    end.day === daysInMonth(end.year, end.month)
  ) {
    return `${monthNames[start.month - 1]} ${start.year}`;
  }
  if (start.year === end.year && start.month === end.month) {
    return `${start.day}–${end.day} ${monthNamesGenitive[start.month - 1]} ${start.year}`;
  }
  return `${formatShortDate(start)} – ${formatShortDate(end)}`;
}

function documentBankName(document: ImportDocumentListItemDto): string {
  return (
    document.account?.bankName ??
    document.detectedBankName ??
    "Банк не определён"
  );
}

function documentSummaryLabel(documents: ImportDocumentListDto): string {
  const total = `${documents.summary.totalDocumentCount} ${documentNoun(
    documents.summary.totalDocumentCount,
  )}`;
  return documents.summary.attentionDocumentCount > 0
    ? `${total} · ${documents.summary.attentionDocumentCount} требуют действия`
    : total;
}

function documentNoun(count: number): string {
  const remainder100 = count % 100;
  const remainder10 = count % 10;
  if (remainder100 >= 11 && remainder100 <= 14) {
    return "документов";
  }
  if (remainder10 === 1) {
    return "документ";
  }
  if (remainder10 >= 2 && remainder10 <= 4) {
    return "документа";
  }
  return "документов";
}

function formatUploadedDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function isoDateParts(value: string): {
  day: number;
  month: number;
  year: number;
} {
  return {
    year: Number(value.slice(0, 4)),
    month: Number(value.slice(5, 7)),
    day: Number(value.slice(8, 10)),
  };
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function formatShortDate(parts: {
  day: number;
  month: number;
  year: number;
}): string {
  return `${parts.day} ${monthNamesGenitive[parts.month - 1]} ${parts.year}`;
}

const monthNames = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
];

const monthNamesGenitive = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];
