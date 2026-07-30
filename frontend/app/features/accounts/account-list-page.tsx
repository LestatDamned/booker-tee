import { useRef, useState, type FormEvent, type RefObject } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { AppShell } from "../../shell/app-shell";
import { ActionStack } from "../../ui/action-stack/action-stack";
import { Button, ButtonLink } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../../ui/field/field";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../../ui/field/form-error-summary";
import { Icon } from "../../ui/icon/icon";
import { MoneyValue, type MoneyTone } from "../../ui/money-value/money-value";
import { PageHeader } from "../../ui/page-header/page-header";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import {
  changeAccountLifecycle,
  createAccount,
  type AccountLifecycleAction,
  type AccountDirectoryDto,
  type AccountSummaryDto,
  type AccountType,
  type CreateAccountDraft,
} from "./api/accounts-api";
import { validateAccountDraft, type AccountFieldErrors } from "./account-form";
import styles from "./account-list-page.module.css";

type FieldErrors = AccountFieldErrors;

const accountTypeLabels: Record<AccountType, string> = {
  cash: "Наличные",
  card: "Карта",
  deposit: "Вклад",
  checking: "Расчётный",
  other: "Другой",
};

export function AccountListPage({
  directory,
  session,
}: {
  directory: AccountDirectoryDto;
  session: SessionDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const nameRef = useRef<HTMLInputElement>(null);
  const typeRef = useRef<HTMLSelectElement>(null);
  const currencyRef = useRef<HTMLInputElement>(null);
  const initialBalanceRef = useRef<HTMLInputElement>(null);
  const [accounts, setAccounts] = useState(directory.items);
  const [draft, setDraft] = useState<CreateAccountDraft>(() =>
    emptyDraft(session, directory),
  );
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [lifecyclePendingId, setLifecyclePendingId] = useState<string | null>(
    null,
  );
  const [archiveCandidate, setArchiveCandidate] =
    useState<AccountSummaryDto | null>(null);
  const [lifecycleMessage, setLifecycleMessage] = useState<string | null>(null);
  const query = accountListQuery(location.search);
  const activeCount = accounts.filter((account) => account.isActive).length;
  const archivedCount = accounts.length - activeCount;
  const visibleAccounts = accounts.filter(
    (account) =>
      account.isActive === (query.view === "active") &&
      accountMatchesSearch(account, query.search),
  );

  const changeDraft = <FieldName extends keyof CreateAccountDraft>(
    field: FieldName,
    value: CreateAccountDraft[FieldName],
  ) => {
    setDraft((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
    setSuccessMessage(null);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = validateAccountDraft(draft);
    setFieldErrors(nextErrors);
    setSubmitError(null);
    setSuccessMessage(null);
    const invalidField = firstInvalidField(nextErrors);
    if (invalidField) {
      fieldRefs({
        currencyRef,
        initialBalanceRef,
        nameRef,
        typeRef,
      })[invalidField].current?.focus();
      return;
    }

    setPending(true);
    const result = await createAccount({
      csrfToken: session.csrfToken,
      draft,
    });
    setPending(false);
    if (result.status === "success") {
      setAccounts((current) => insertCommittedAccount(current, result.account));
      setDraft(emptyDraft(session, directory));
      setFieldErrors({});
      setSuccessMessage(`Счёт «${result.account.name}» создан.`);
      setCreateOpen(false);
      void navigate({ pathname: location.pathname, search: "", hash: "" });
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/accounts");
      return;
    }
    if (result.status === "forbidden") {
      setSubmitError(result.message);
      return;
    }
    const serverErrors = accountFieldErrors(result.fieldErrors);
    setFieldErrors(serverErrors);
    setSubmitError(result.message);
    const serverInvalidField = firstInvalidField(serverErrors);
    if (serverInvalidField) {
      fieldRefs({
        currencyRef,
        initialBalanceRef,
        nameRef,
        typeRef,
      })[serverInvalidField].current?.focus();
    }
  };

  const summaryErrors = formSummaryErrors(fieldErrors);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("search");
    const normalized =
      typeof value === "string" ? value.trim().replace(/\s+/g, " ") : "";
    void navigate(accountListUrl(query.view, normalized));
  }

  async function runLifecycle(
    account: AccountSummaryDto,
    action: AccountLifecycleAction,
  ) {
    setLifecyclePendingId(account.id);
    setLifecycleMessage(null);
    const result = await changeAccountLifecycle({
      account,
      action,
      csrfToken: session.csrfToken,
    });
    setLifecyclePendingId(null);
    if (result.status === "success") {
      setAccounts((current) =>
        current.map((item) =>
          item.id === result.account.id ? result.account : item,
        ),
      );
      setArchiveCandidate(null);
      setLifecycleMessage(
        action === "archive"
          ? `Счёт «${result.account.name}» перенесён в архив.`
          : `Счёт «${result.account.name}» восстановлен.`,
      );
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/accounts");
      return;
    }
    setArchiveCandidate(null);
    setLifecycleMessage(result.message);
  }

  return (
    <AppShell session={session}>
      <main className={styles.page}>
        <section className={styles.workbench}>
          <div className={styles.workbenchHeader}>
            <PageHeader
              description="Где хранятся деньги и как меняется остаток по подтверждённым операциям."
              eyebrow={accountCountLabel(visibleAccounts.length)}
              title="Счета"
            />
          </div>

          <section aria-label="Инструменты списка" className={styles.listTools}>
            <div className={styles.listToolActions}>
              <form
                aria-label="Поиск счетов"
                className={styles.searchForm}
                onSubmit={submitSearch}
                role="search"
              >
                <label className="visually-hidden" htmlFor="account-search">
                  Поиск по названию, типу или валюте
                </label>
                <input
                  defaultValue={query.search}
                  id="account-search"
                  key={query.search}
                  name="search"
                  placeholder="Поиск по названию, типу или валюте"
                  type="search"
                />
                <Button icon="search" type="submit">
                  Найти
                </Button>
              </form>

              <nav aria-label="Состояние счетов" className={styles.tabs}>
                <Link
                  aria-current={query.view === "active" ? "page" : undefined}
                  to={accountListUrl("active", query.search)}
                >
                  Активные <span>{activeCount}</span>
                </Link>
                <Link
                  aria-current={query.view === "archived" ? "page" : undefined}
                  to={accountListUrl("archived", query.search)}
                >
                  Архив <span>{archivedCount}</span>
                </Link>
              </nav>

              {directory.capabilities.canCreate ? (
                <Button
                  aria-haspopup="dialog"
                  icon="plus"
                  onClick={() => setCreateOpen(true)}
                  tone="primary"
                >
                  Новый счёт
                </Button>
              ) : null}
            </div>
          </section>

          {!directory.capabilities.canCreate ? (
            <section className={styles.readonlyNotice}>
              <Icon name="information" size={22} />
              <div>
                <strong>Счета доступны только для просмотра</strong>
                <p>
                  Создавать счета может владелец, администратор или редактор.
                </p>
              </div>
            </section>
          ) : null}

          <p className={styles.liveMessage} aria-live="polite">
            {successMessage ?? lifecycleMessage}
          </p>

          {accounts.length === 0 ? (
            <section className={styles.emptyState}>
              <Icon name="accounts" size={30} />
              <div>
                <h2>Пока нет счетов</h2>
                <p>
                  Добавьте место, где хранятся деньги: карту, вклад, наличные
                  или расчётный счёт.
                </p>
              </div>
              {directory.capabilities.canCreate ? (
                <Button
                  icon="plus"
                  onClick={() => setCreateOpen(true)}
                  tone="primary"
                >
                  Добавить первый счёт
                </Button>
              ) : null}
            </section>
          ) : visibleAccounts.length > 0 ? (
            <>
              <AccountTable
                accounts={visibleAccounts}
                lifecyclePendingId={lifecyclePendingId}
                onArchive={setArchiveCandidate}
                onRestore={(account) => void runLifecycle(account, "restore")}
              />
              <AccountMobileList
                accounts={visibleAccounts}
                lifecyclePendingId={lifecyclePendingId}
                onArchive={setArchiveCandidate}
                onRestore={(account) => void runLifecycle(account, "restore")}
              />
            </>
          ) : (
            <section className={styles.filteredEmpty}>
              <Icon name="search" size={28} />
              <h2>
                {query.search
                  ? "По этому запросу счетов нет"
                  : query.view === "archived"
                    ? "Архив пока пуст"
                    : "Активных счетов нет"}
              </h2>
              <p>
                {query.search
                  ? "Измените запрос или очистите поиск."
                  : "Счета появятся здесь после изменения их состояния."}
              </p>
              {query.search ? (
                <Link
                  className={styles.resetLink}
                  to={accountListUrl(query.view, "")}
                >
                  Очистить поиск
                </Link>
              ) : null}
            </section>
          )}
        </section>
      </main>

      {createOpen ? (
        <WorkbenchPanel
          description="Название, тип, валюта и остаток до первой операции."
          disabled={pending}
          onClose={() => setCreateOpen(false)}
          title="Новый счёт"
        >
          <form
            className={styles.createForm}
            data-account-create
            noValidate
            onSubmit={submit}
          >
            {(submitError || summaryErrors.length > 0) && (
              <FormErrorSummary
                errors={summaryErrors}
                message={
                  submitError ?? "Проверьте поля нового счёта и повторите."
                }
              />
            )}
            <div className={styles.formGrid}>
              <Field
                error={fieldErrors.name}
                errorId="account-name-error"
                htmlFor="account-name"
                label="Название"
                required
              >
                <input
                  ref={nameRef}
                  id="account-name"
                  aria-describedby={
                    fieldErrors.name ? "account-name-error" : undefined
                  }
                  aria-invalid={Boolean(fieldErrors.name)}
                  autoFocus
                  autoComplete="off"
                  disabled={pending}
                  maxLength={255}
                  name="name"
                  placeholder="Основная карта"
                  required
                  value={draft.name}
                  onChange={(event) => changeDraft("name", event.target.value)}
                />
              </Field>
              <Field
                error={fieldErrors.accountType}
                errorId="account-type-error"
                htmlFor="account-type"
                label="Тип"
                required
              >
                <select
                  ref={typeRef}
                  id="account-type"
                  aria-describedby={
                    fieldErrors.accountType ? "account-type-error" : undefined
                  }
                  aria-invalid={Boolean(fieldErrors.accountType)}
                  disabled={pending}
                  name="accountType"
                  required
                  value={draft.accountType}
                  onChange={(event) =>
                    changeDraft(
                      "accountType",
                      event.target.value as AccountType,
                    )
                  }
                >
                  {directory.accountTypes.map((accountType) => (
                    <option key={accountType} value={accountType}>
                      {accountTypeLabels[accountType]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field
                error={fieldErrors.currency}
                errorId="account-currency-error"
                hint="Трёхбуквенный код, например RUB."
                htmlFor="account-currency"
                label="Валюта"
                required
              >
                <input
                  ref={currencyRef}
                  id="account-currency"
                  aria-describedby={
                    fieldErrors.currency ? "account-currency-error" : undefined
                  }
                  aria-invalid={Boolean(fieldErrors.currency)}
                  autoCapitalize="characters"
                  autoComplete="off"
                  disabled={pending}
                  maxLength={3}
                  name="currency"
                  required
                  value={draft.currency}
                  onChange={(event) =>
                    changeDraft("currency", event.target.value.toUpperCase())
                  }
                />
              </Field>
              <Field
                error={fieldErrors.initialBalance}
                errorId="account-initial-balance-error"
                hint="Остаток до первой операции в Booker Tee."
                htmlFor="account-initial-balance"
                label="Начальный баланс"
                required
              >
                <input
                  ref={initialBalanceRef}
                  id="account-initial-balance"
                  aria-describedby={
                    fieldErrors.initialBalance
                      ? "account-initial-balance-error"
                      : undefined
                  }
                  aria-invalid={Boolean(fieldErrors.initialBalance)}
                  autoComplete="off"
                  disabled={pending}
                  inputMode="decimal"
                  name="initialBalance"
                  required
                  value={draft.initialBalance}
                  onChange={(event) =>
                    changeDraft("initialBalance", event.target.value)
                  }
                />
              </Field>
            </div>
            <div className={styles.formActions}>
              <Button
                disabled={pending}
                icon="plus"
                isLoading={pending}
                tone="primary"
                type="submit"
              >
                {pending ? "Создаём…" : "Создать счёт"}
              </Button>
            </div>
          </form>
        </WorkbenchPanel>
      ) : null}

      {archiveCandidate ? (
        <ConfirmationDialog
          confirmLabel="Перенести в архив"
          description={`История и баланс счёта «${archiveCandidate.name}» сохранятся, но счёт нельзя будет выбирать для новых операций и импортов.`}
          onCancel={() => setArchiveCandidate(null)}
          onConfirm={() => void runLifecycle(archiveCandidate, "archive")}
          pending={lifecyclePendingId === archiveCandidate.id}
          title="Перенести счёт в архив?"
        />
      ) : null}
    </AppShell>
  );
}

type AccountListProps = {
  accounts: AccountSummaryDto[];
  lifecyclePendingId: string | null;
  onArchive: (account: AccountSummaryDto) => void;
  onRestore: (account: AccountSummaryDto) => void;
};

function AccountTable({
  accounts,
  lifecyclePendingId,
  onArchive,
  onRestore,
}: AccountListProps) {
  return (
    <div className={styles.tableRegion}>
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
                <a
                  className={styles.accountLink}
                  href={`/app/accounts/${account.id}`}
                >
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
                  pending={lifecyclePendingId === account.id}
                  onArchive={onArchive}
                  onRestore={onRestore}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AccountMobileList({
  accounts,
  lifecyclePendingId,
  onArchive,
  onRestore,
}: AccountListProps) {
  return (
    <ol aria-label="Счета текущего workspace" className={styles.mobileList}>
      {accounts.map((account) => (
        <li key={account.id}>
          <article className={styles.mobileRecord} data-account-record>
            <div className={styles.mobileHeading}>
              <div>
                <a
                  className={styles.accountLink}
                  href={`/app/accounts/${account.id}`}
                >
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
                pending={lifecyclePendingId === account.id}
                onArchive={onArchive}
                onRestore={onRestore}
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

type AccountListView = "active" | "archived";

function accountListQuery(search: string): {
  search: string;
  view: AccountListView;
} {
  const params = new URLSearchParams(search);
  return {
    search: params.get("search")?.trim() ?? "",
    view: params.get("view") === "archived" ? "archived" : "active",
  };
}

function accountListUrl(view: AccountListView, search: string) {
  const params = new URLSearchParams();
  if (view === "archived") params.set("view", "archived");
  if (search) params.set("search", search);
  const query = params.toString();
  return query ? `?${query}` : ".";
}

function accountMatchesSearch(account: AccountSummaryDto, search: string) {
  if (!search) return true;
  const normalized = search.toLocaleLowerCase("ru-RU");
  return [
    account.name,
    accountTypeLabels[account.accountType],
    account.currency,
  ].some((value) => value.toLocaleLowerCase("ru-RU").includes(normalized));
}

function emptyDraft(
  session: SessionDto,
  directory: AccountDirectoryDto,
): CreateAccountDraft {
  return {
    name: "",
    accountType: directory.accountTypes[0] ?? "card",
    currency: session.workspace.defaultCurrency,
    initialBalance: "0.00",
  };
}

function accountFieldErrors(
  fieldErrors: Record<string, string[]>,
): FieldErrors {
  const errors: FieldErrors = {};
  const mappings: Array<[keyof CreateAccountDraft, string]> = [
    ["accountType", "accountType"],
    ["currency", "currency"],
    ["initialBalance", "initialBalance"],
    ["name", "name"],
  ];
  for (const [field, serverField] of mappings) {
    const message = fieldErrors[serverField]?.[0];
    if (message) errors[field] = message;
  }
  return errors;
}

function firstInvalidField(
  errors: FieldErrors,
): keyof CreateAccountDraft | null {
  for (const field of [
    "name",
    "accountType",
    "currency",
    "initialBalance",
  ] as const) {
    if (errors[field]) return field;
  }
  return null;
}

function fieldRefs({
  currencyRef,
  initialBalanceRef,
  nameRef,
  typeRef,
}: {
  currencyRef: RefObject<HTMLInputElement | null>;
  initialBalanceRef: RefObject<HTMLInputElement | null>;
  nameRef: RefObject<HTMLInputElement | null>;
  typeRef: RefObject<HTMLSelectElement | null>;
}): Record<keyof CreateAccountDraft, RefObject<HTMLElement | null>> {
  return {
    accountType: typeRef,
    currency: currencyRef,
    initialBalance: initialBalanceRef,
    name: nameRef,
  };
}

function formSummaryErrors(errors: FieldErrors): FormErrorSummaryItem[] {
  const fields: Array<{
    field: keyof CreateAccountDraft;
    fieldId: string;
    label: string;
  }> = [
    { field: "name", fieldId: "account-name", label: "Название" },
    { field: "accountType", fieldId: "account-type", label: "Тип" },
    { field: "currency", fieldId: "account-currency", label: "Валюта" },
    {
      field: "initialBalance",
      fieldId: "account-initial-balance",
      label: "Начальный баланс",
    },
  ];
  return fields.flatMap(({ field, fieldId, label }) =>
    errors[field] ? [{ fieldId, label, message: errors[field] }] : [],
  );
}

function insertCommittedAccount(
  accounts: AccountSummaryDto[],
  account: AccountSummaryDto,
): AccountSummaryDto[] {
  const firstArchived = accounts.findIndex((item) => !item.isActive);
  if (firstArchived === -1) {
    return [...accounts, account];
  }
  return [
    ...accounts.slice(0, firstArchived),
    account,
    ...accounts.slice(firstArchived),
  ];
}

function accountCountLabel(count: number): string {
  return `${count} ${pluralize(count, "счёт", "счёта", "счетов")}`;
}

function movementCountLabel(count: number): string {
  return `${count} ${pluralize(count, "проводка", "проводки", "проводок")}`;
}

function pluralize(
  count: number,
  one: string,
  few: string,
  many: string,
): string {
  const tens = count % 100;
  const units = count % 10;
  if (tens >= 11 && tens <= 14) return many;
  if (units === 1) return one;
  if (units >= 2 && units <= 4) return few;
  return many;
}
