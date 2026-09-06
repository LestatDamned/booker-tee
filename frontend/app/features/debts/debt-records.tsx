import { Link, useLocation } from "react-router";

import { formatMoneyAmount } from "../../shared/money/format-money";
import { RouterButtonLink } from "../../ui/button/button";
import { MoneyValue } from "../../ui/money-value/money-value";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import { StatusLabel } from "../../ui/status-label/status-label";
import type { DebtSummaryDto } from "./api/debts-api";
import {
  debtDirectionLabel,
  debtKindLabels,
  debtStatusLabels,
} from "./debt-model";
import styles from "./debts.module.css";

export function DebtRecords({ debts }: { debts: DebtSummaryDto[] }) {
  return (
    <ResponsiveRecordCollection
      mobileList={<DebtMobileList debts={debts} />}
      table={<DebtTable debts={debts} />}
    />
  );
}

function DebtTable({ debts }: { debts: DebtSummaryDto[] }) {
  const { search } = useLocation();
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">Долг</th>
          <th scope="col">Направление</th>
          <th scope="col">Состояние</th>
          <th scope="col">Остаток</th>
          <th aria-label="Действия" scope="col" />
        </tr>
      </thead>
      <tbody>
        {debts.map((debt) => (
          <tr key={debt.accountId}>
            <td>
              <Link data-record-identity to={debtHref(debt.accountId, search)}>
                {debt.name}
              </Link>
              <span className={styles.secondary}>
                {debtKindLabels[debt.kind]}
              </span>
            </td>
            <td>{debtDirectionLabel(debt.kind)}</td>
            <td>
              <DebtStatus debt={debt} />
            </td>
            <td>
              <MoneyValue
                amount={formatMoneyAmount(debt.outstanding, null)}
                currency={debt.currency}
                tone={debt.kind === "loan_receivable" ? "income" : "expense"}
              />
            </td>
            <td>
              <RouterButtonLink to={debtHref(debt.accountId, search)}>
                Открыть
              </RouterButtonLink>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DebtMobileList({ debts }: { debts: DebtSummaryDto[] }) {
  const { search } = useLocation();
  return (
    <ol aria-label="Долги">
      {debts.map((debt) => (
        <li key={debt.accountId}>
          <article data-responsive-record>
            <div className={styles.mobileHeader}>
              <div>
                <Link
                  data-record-identity
                  to={debtHref(debt.accountId, search)}
                >
                  {debt.name}
                </Link>
                <span className={styles.secondary}>
                  {debtKindLabels[debt.kind]}
                </span>
              </div>
              <DebtStatus debt={debt} />
            </div>
            <div className={styles.mobileFacts}>
              <span>{debtDirectionLabel(debt.kind)}</span>
              <MoneyValue
                amount={formatMoneyAmount(debt.outstanding, null)}
                currency={debt.currency}
                tone={debt.kind === "loan_receivable" ? "income" : "expense"}
              />
            </div>
            <RouterButtonLink to={debtHref(debt.accountId, search)}>
              Открыть долг
            </RouterButtonLink>
          </article>
        </li>
      ))}
    </ol>
  );
}

function DebtStatus({ debt }: { debt: DebtSummaryDto }) {
  const tone =
    debt.status === "active"
      ? "information"
      : debt.status === "archived"
        ? "neutral"
        : "success";
  return <StatusLabel tone={tone}>{debtStatusLabels[debt.status]}</StatusLabel>;
}

function debtHref(id: string, search: string): string {
  const query = new URLSearchParams(search);
  query.delete("page");
  return `/debts/${id}${query.size ? `?${query}` : ""}`;
}
