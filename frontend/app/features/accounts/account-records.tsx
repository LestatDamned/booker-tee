import { formatMoneyAmount } from "../../shared/money/format-money";
import { ActionStack } from "../../ui/action-stack/action-stack";
import { Button, ButtonLink } from "../../ui/button/button";
import { MoneyValue, type MoneyTone } from "../../ui/money-value/money-value";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import { accountTypeLabels, movementCountLabel } from "./account-labels";
import styles from "./account-list-page.module.css";
import type { AccountSummaryDto } from "./api/accounts-api";

type AccountRecordsProps = {
  accounts: AccountSummaryDto[];
  lifecyclePendingId: string | null;
  onArchive: (account: AccountSummaryDto) => void;
  onRestore: (account: AccountSummaryDto) => void;
};

export function AccountRecords(props: AccountRecordsProps) {
  return (
    <ResponsiveRecordCollection
      mobileList={<AccountMobileList {...props} />}
      table={<AccountTable {...props} />}
    />
  );
}

function AccountTable({
  accounts,
  lifecyclePendingId,
  onArchive,
  onRestore,
}: AccountRecordsProps) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">Счета текущего workspace</caption>
      <thead>
        <tr>
          <th scope="col">Счёт</th>
          <th scope="col">Проводки</th>
          <th scope="col">Баланс</th>
          <th scope="col">
            <span className="visually-hidden">Действие</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {accounts.map((account) => (
          <tr data-account-record key={account.id}>
            <th scope="row">
              <a data-record-identity href={`/app/accounts/${account.id}`}>
                {account.name}
              </a>
              <span className={styles.accountMeta}>
                {accountTypeLabels[account.accountType]} · {account.currency}
              </span>
            </th>
            <td>{movementCountLabel(account.movementCount)}</td>
            <td className={styles.balanceCell}>
              <span className={styles.balanceValue} data-account-balance>
                <AccountBalance account={account} />
              </span>
            </td>
            <td className={styles.actionCell}>
              <AccountActions
                account={account}
                onArchive={onArchive}
                onRestore={onRestore}
                pending={lifecyclePendingId === account.id}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AccountMobileList({
  accounts,
  lifecyclePendingId,
  onArchive,
  onRestore,
}: AccountRecordsProps) {
  return (
    <ol aria-label="Счета текущего workspace">
      {accounts.map((account) => (
        <li key={account.id}>
          <article data-account-record data-responsive-record>
            <div className={styles.mobileHeading}>
              <div>
                <a data-record-identity href={`/app/accounts/${account.id}`}>
                  {account.name}
                </a>
                <span className={styles.accountMeta}>
                  {accountTypeLabels[account.accountType]} · {account.currency}
                </span>
              </div>
              <span className={styles.mobileBalanceValue}>
                <AccountBalance account={account} />
              </span>
            </div>
            <div className={styles.mobileFooter}>
              <span>{movementCountLabel(account.movementCount)}</span>
              <AccountActions
                account={account}
                onArchive={onArchive}
                onRestore={onRestore}
                pending={lifecyclePendingId === account.id}
              />
            </div>
          </article>
        </li>
      ))}
    </ol>
  );
}

function AccountActions({
  account,
  pending,
  onArchive,
  onRestore,
}: {
  account: AccountSummaryDto;
  pending: boolean;
  onArchive: (account: AccountSummaryDto) => void;
  onRestore: (account: AccountSummaryDto) => void;
}) {
  return (
    <ActionStack
      orientation="row"
      primary={
        <ButtonLink
          data-account-action
          href={`/app/accounts/${account.id}`}
          tone="secondary"
        >
          Открыть
        </ButtonLink>
      }
      secondary={
        account.capabilities.canArchive ? (
          <Button
            disabled={pending}
            onClick={() => onArchive(account)}
            tone="dangerSecondary"
          >
            В архив
          </Button>
        ) : account.capabilities.canRestore ? (
          <Button
            disabled={pending}
            isLoading={pending}
            onClick={() => onRestore(account)}
            tone="secondary"
          >
            Восстановить
          </Button>
        ) : undefined
      }
    />
  );
}

function AccountBalance({ account }: { account: AccountSummaryDto }) {
  const tone: MoneyTone =
    account.balanceDirection === "positive"
      ? "balancePositive"
      : account.balanceDirection === "negative"
        ? "expense"
        : "neutral";
  return (
    <MoneyValue
      amount={formatMoneyAmount(account.balance, null)}
      currency={account.currency}
      tone={tone}
    />
  );
}
