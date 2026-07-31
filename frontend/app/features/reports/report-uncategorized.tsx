import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";

import { formatMoneyAmount } from "../../shared/money/format-money";
import { ButtonLink } from "../../ui/button/button";
import { MoneyValue } from "../../ui/money-value/money-value";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import { Tag } from "../../ui/tag/tag";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchPagination } from "../../ui/workbench-pagination/workbench-pagination";
import type { ReportOverviewDto } from "./api/reports-api";
import {
  reportUncategorizedPage,
  reportUncategorizedPageSearch,
} from "./report-filter-query";
import styles from "./reports-page.module.css";

type Operation = ReportOverviewDto["uncategorized"]["items"][number];

export function ReportUncategorized({
  overview,
}: {
  overview: ReportOverviewDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const page = overview.uncategorized;
  const requestedPage = reportUncategorizedPage(location.search);

  useEffect(() => {
    if (requestedPage === page.page) return;
    void navigate(
      {
        pathname: location.pathname,
        search: reportUncategorizedPageSearch(location.search, page.page),
      },
      { replace: true },
    );
  }, [location.pathname, location.search, navigate, page.page, requestedPage]);

  return (
    <section className={styles.uncategorizedSection}>
      <header className={styles.breakdownHeading}>
        <div>
          <p className={styles.sectionEyebrow}>Требует классификации</p>
          <h2>Операции без категории</h2>
        </div>
        <p>
          Только подтверждённые операции, влияющие на результат в{" "}
          {overview.summary.currency}.
        </p>
      </header>

      {page.total === 0 ? (
        <WorkbenchEmptyState
          icon="categories"
          title="Все операции распределены"
        >
          По текущим условиям подтверждённых операций без категории нет.
        </WorkbenchEmptyState>
      ) : (
        <>
          <ResponsiveRecordCollection
            mobileList={<OperationCards items={page.items} />}
            table={<OperationTable items={page.items} />}
          />
          <WorkbenchPagination
            ariaLabel="Страницы операций без категории"
            currentPage={page.page}
            getPageHref={(nextPage) =>
              reportUncategorizedPageSearch(location.search, nextPage)
            }
            hasNext={page.hasNext}
            hasPrevious={page.hasPrevious}
            summary={pageRange(page)}
            totalPages={page.totalPages}
          />
        </>
      )}
    </section>
  );
}

function OperationTable({ items }: { items: Operation[] }) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">Операции без категории</caption>
      <thead>
        <tr>
          <th scope="col">Дата</th>
          <th scope="col">Операция</th>
          <th scope="col">Источник</th>
          <th className={styles.moneyColumn} scope="col">
            Сумма
          </th>
          <th className={styles.actionColumn} scope="col">
            Действие
          </th>
        </tr>
      </thead>
      <tbody>
        {items.map((operation) => (
          <tr key={operation.operationId}>
            <td>
              <time dateTime={operation.operationDate}>
                {formatDate(operation.operationDate)}
              </time>
            </td>
            <td>
              <strong>{operation.description}</strong>
              <div className={styles.operationMeta}>
                <Tag tone={operationTone(operation.operationType)}>
                  {operationTypeLabel(operation.operationType)}
                </Tag>
              </div>
            </td>
            <td>{sourceLabel(operation.source)}</td>
            <td className={styles.moneyColumn}>
              <OperationMoney operation={operation} />
            </td>
            <td className={styles.actionColumn}>{correctionView(operation)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function OperationCards({ items }: { items: Operation[] }) {
  return (
    <ol className={styles.breakdownCards}>
      {items.map((operation) => (
        <li data-responsive-record key={operation.operationId}>
          <div className={styles.operationCardHeading}>
            <div>
              <time dateTime={operation.operationDate}>
                {formatDate(operation.operationDate)}
              </time>
              <strong>{operation.description}</strong>
            </div>
            <OperationMoney operation={operation} />
          </div>
          <div className={styles.operationMeta}>
            <Tag tone={operationTone(operation.operationType)}>
              {operationTypeLabel(operation.operationType)}
            </Tag>
            <span>{sourceLabel(operation.source)}</span>
          </div>
          <div className={styles.operationAction}>
            {correctionView(operation)}
          </div>
        </li>
      ))}
    </ol>
  );
}

function OperationMoney({ operation }: { operation: Operation }) {
  return (
    <MoneyValue
      amount={formatMoneyAmount(
        operation.signedAmount,
        operation.operationType === "income"
          ? "income"
          : operation.operationType === "expense"
            ? "expense"
            : null,
      )}
      currency={operation.currency}
      tone={operationTone(operation.operationType)}
    />
  );
}

function correctionView(operation: Operation) {
  if (operation.capabilities.canCorrect) {
    if (operation.source === "manual") {
      return (
        <ButtonLink
          href={`/app/ledger/manual?operation_id=${operation.operationId}#operation-${operation.operationId}`}
          icon="edit"
          tone="secondary"
        >
          Открыть операцию
        </ButtonLink>
      );
    }
    if (operation.source === "bank_pdf" && operation.accountId) {
      return (
        <ButtonLink
          href={`/app/accounts/${operation.accountId}`}
          icon="edit"
          tone="secondary"
        >
          Открыть счёт
        </ButtonLink>
      );
    }
  }
  return (
    <span className={styles.readonlyReason}>{readonlyReason(operation)}</span>
  );
}

function readonlyReason(operation: Operation): string {
  switch (operation.capabilities.readonlyReasonCode) {
    case "financial_write_forbidden":
      return "Только чтение: недостаточно прав.";
    case "system_operation":
      return "Системная операция.";
    case "correction_account_unavailable":
      return "Счёт для исправления недоступен.";
    default:
      return "Исправление недоступно.";
  }
}

function operationTypeLabel(type: Operation["operationType"]): string {
  if (type === "income") return "Доход";
  if (type === "expense") return "Расход";
  if (type === "adjustment") return "Корректировка";
  return "Перевод";
}

function operationTone(
  type: Operation["operationType"],
): "income" | "expense" | "adjustment" | "transfer" {
  if (type === "income") return "income";
  if (type === "expense") return "expense";
  if (type === "adjustment") return "adjustment";
  return "transfer";
}

function sourceLabel(source: Operation["source"]): string {
  if (source === "manual") return "Вручную";
  if (source === "bank_pdf") return "Импорт";
  return "Система";
}

function pageRange(page: ReportOverviewDto["uncategorized"]): string {
  if (page.total === 0) return "0 операций";
  const start = (page.page - 1) * page.pageSize + 1;
  const end = Math.min(page.page * page.pageSize, page.total);
  return `${start}–${end} из ${page.total}`;
}

function formatDate(value: string): string {
  const [year, month, day] = value.split("-");
  return `${day}.${month}.${year}`;
}
