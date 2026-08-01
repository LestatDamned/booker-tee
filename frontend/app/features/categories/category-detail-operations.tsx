import { useLocation, useNavigate } from "react-router";

import { formatIsoDate } from "../../shared/date/format-date";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { MoneyValue } from "../../ui/money-value/money-value";
import { ReadOnlyFinancialRow } from "../../ui/read-only-financial-row/read-only-financial-row";
import { Tag, type TagTone } from "../../ui/tag/tag";
import { WorkbenchPagination } from "../../ui/workbench-pagination/workbench-pagination";
import type { CategoryDetailDto } from "./api/category-detail-api";
import {
  categoryDetailPageSizeUrl,
  categoryDetailPageUrl,
} from "./category-detail-query";
import styles from "./category-detail-page.module.css";

type CategoryOperation = CategoryDetailDto["operations"]["items"][number];

const operationLabels = {
  adjustment: "Корректировка",
  expense: "Расход",
  income: "Доход",
  transfer: "Перевод",
} as const;

export function CategoryOperations({ detail }: { detail: CategoryDetailDto }) {
  return (
    <ol className={styles.operationList}>
      {detail.operations.items.map((operation) => (
        <li key={operation.operationId}>
          <ReadOnlyFinancialRow
            context={operation.accountName}
            date={formatIsoDate(operation.operationDate)}
            dateTime={operation.operationDate}
            description={operation.description}
            details={operationDetails(operation)}
            id={`operation-${operation.operationId}`}
            status={
              <Tag tone={kindTone(operation.operationType)}>
                {operationLabels[operation.operationType]}
              </Tag>
            }
            value={<OperationMoney operation={operation} />}
          />
        </li>
      ))}
    </ol>
  );
}

export function CategoryOperationsPagination({
  disabled,
  detail,
}: {
  disabled: boolean;
  detail: CategoryDetailDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const pageSizeOptions = [20, 50, 100] as const;
  const showPageSize =
    pageSizeOptions.includes(detail.operations.pageSize as 20 | 50 | 100) &&
    pageSizeOptions.some((option) => detail.operations.total > option);
  const start =
    detail.operations.total === 0
      ? 0
      : (detail.operations.page - 1) * detail.operations.pageSize + 1;
  const end = Math.min(
    detail.operations.page * detail.operations.pageSize,
    detail.operations.total,
  );
  return (
    <WorkbenchPagination
      ariaLabel="Страницы операций категории"
      currentPage={detail.operations.page}
      getPageHref={(page) =>
        categoryDetailPageUrl(location.pathname, location.search, page)
      }
      hasNext={detail.operations.hasNext}
      hasPrevious={detail.operations.hasPrevious}
      {...(showPageSize
        ? {
            pageSize: {
              disabled,
              id: "category-operation-page-size",
              onChange: (pageSize: number) => {
                if (!pageSizeOptions.includes(pageSize as 20 | 50 | 100))
                  return;
                void navigate(
                  categoryDetailPageSizeUrl(
                    location.pathname,
                    location.search,
                    pageSize,
                  ),
                );
              },
              options: pageSizeOptions,
              value: detail.operations.pageSize,
            },
          }
        : {})}
      summary={
        detail.operations.total === 0
          ? "0 операций"
          : `${start}–${end} из ${detail.operations.total}`
      }
      totalPages={detail.operations.totalPages}
    />
  );
}

function OperationMoney({ operation }: { operation: CategoryOperation }) {
  return (
    <MoneyValue
      amount={formatMoneyAmount(
        operation.signedAmount,
        operation.operationType === "income" ||
          operation.operationType === "expense"
          ? operation.operationType
          : null,
      )}
      currency={operation.currency}
      tone={operation.operationType}
    />
  );
}

function operationDetails(operation: CategoryOperation) {
  if (!operation.propertyName && operation.operationType !== "transfer") {
    return undefined;
  }
  return (
    <>
      {operation.propertyName ? (
        <span>Объект: {operation.propertyName}</span>
      ) : null}
      {operation.operationType === "transfer" ? (
        <span>Не влияет на прибыль</span>
      ) : null}
    </>
  );
}

function kindTone(kind: keyof typeof operationLabels): TagTone {
  return kind;
}
