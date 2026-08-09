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
              <strong>{debt.name}</strong>
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
              <RouterButtonLink to={`/debts/${debt.accountId}`}>
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
  return (
    <ul className={styles.mobileList}>
      {debts.map((debt) => (
        <li key={debt.accountId}>
          <div className={styles.mobileHeader}>
            <div>
              <strong>{debt.name}</strong>
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
          <RouterButtonLink to={`/debts/${debt.accountId}`}>
            Открыть долг
          </RouterButtonLink>
        </li>
      ))}
    </ul>
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
