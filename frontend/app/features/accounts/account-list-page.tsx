import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { Button, RouterButtonLink } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { ToastViewport, useToastQueue } from "../../ui/toast/toast";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import { AccountCreatePanel } from "./account-create-panel";
import { accountCountLabel, accountTypeLabels } from "./account-labels";
import styles from "./account-list-page.module.css";
import { AccountRecords } from "./account-records";
import type {
  AccountDirectoryDto,
  AccountSummaryDto,
} from "./api/accounts-api";
import { useAccountLifecycle } from "./use-account-lifecycle";

export function AccountListPage({
  directory,
  session,
}: {
  directory: AccountDirectoryDto;
  session: SessionDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState(directory.items);
  const [createOpen, setCreateOpen] = useState(false);
  const { dismissToast, showToast, toast } = useToastQueue();
  const lifecycle = useAccountLifecycle({
    csrfToken: session.csrfToken,
    onCommitted: replaceCommitted,
    showToast,
  });
  const query = accountListQuery(location.search);
  const activeCount = accounts.filter((account) => account.isActive).length;
  const archivedCount = accounts.length - activeCount;
  const visibleAccounts = accounts.filter(
    (account) =>
      account.isActive === (query.view === "active") &&
      accountMatchesSearch(account, query.search),
  );

  function replaceCommitted(account: AccountSummaryDto) {
    setAccounts((current) =>
      current.map((item) => (item.id === account.id ? account : item)),
    );
  }

  function commitCreated(account: AccountSummaryDto) {
    setAccounts((current) => insertCommittedAccount(current, account));
    showToast({ message: `Счёт «${account.name}» создан.` });
    setCreateOpen(false);
    void navigate({ pathname: location.pathname, search: "", hash: "" });
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("search");
    const normalized =
      typeof value === "string" ? value.trim().replace(/\s+/g, " ") : "";
    void navigate(accountListUrl(query.view, normalized));
  }

  return (
    <AppShell session={session}>
      <PageFrame>
        <WorkbenchSurface className={styles.workbench}>
          <WorkbenchHeader>
            <PageHeader
              description="Где хранятся деньги и как меняется остаток по подтверждённым операциям."
              eyebrow={accountCountLabel(visibleAccounts.length)}
              title="Счета"
            />
          </WorkbenchHeader>

          <WorkbenchToolbar>
            <div className={styles.listToolActions}>
              <WorkbenchSearch
                ariaLabel="Поиск счетов"
                className={styles.searchPlacement}
                inputId="account-search"
                inputLabel="Поиск по названию, типу или валюте"
                inputProps={{ defaultValue: query.search }}
                key={query.search}
                onSubmit={submitSearch}
                placeholder="Поиск по названию, типу или валюте"
              />

              <SelectionTabs
                as="nav"
                aria-label="Состояние счетов"
                className={styles.accountTabs}
              >
                <SelectionTabLink
                  count={activeCount}
                  selected={query.view === "active"}
                  to={accountListUrl("active", query.search)}
                >
                  Активные
                </SelectionTabLink>
                <SelectionTabLink
                  count={archivedCount}
                  selected={query.view === "archived"}
                  to={accountListUrl("archived", query.search)}
                >
                  Архив
                </SelectionTabLink>
              </SelectionTabs>

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
          </WorkbenchToolbar>

          {!directory.capabilities.canCreate ? (
            <InlineNotice
              className={styles.accountReadonlyNotice}
              title="Счета доступны только для просмотра"
              tone="information"
            >
              Создавать счета может владелец, администратор или редактор.
            </InlineNotice>
          ) : null}

          {lifecycle.failure ? (
            <InlineNotice
              action={
                <Button icon="retry" onClick={lifecycle.retry} tone="secondary">
                  Повторить
                </Button>
              }
              className={styles.accountReadonlyNotice}
              role="alert"
              title="Не удалось изменить состояние счёта"
              tone="danger"
            >
              {lifecycle.failure.message}
            </InlineNotice>
          ) : null}

          {accounts.length === 0 ? (
            <WorkbenchEmptyState
              action={
                directory.capabilities.canCreate ? (
                  <Button
                    icon="plus"
                    onClick={() => setCreateOpen(true)}
                    tone="primary"
                  >
                    Добавить первый счёт
                  </Button>
                ) : undefined
              }
              icon="accounts"
              title="Пока нет счетов"
            >
              Добавьте место, где хранятся деньги: карту, вклад, наличные или
              расчётный счёт.
            </WorkbenchEmptyState>
          ) : visibleAccounts.length > 0 ? (
            <AccountRecords
              accounts={visibleAccounts}
              lifecyclePendingId={lifecycle.pendingId}
              onArchive={lifecycle.requestArchive}
              onRestore={lifecycle.restore}
            />
          ) : (
            <WorkbenchEmptyState
              action={
                query.search ? (
                  <RouterButtonLink
                    icon="search"
                    to={accountListUrl(query.view, "")}
                  >
                    Очистить поиск
                  </RouterButtonLink>
                ) : undefined
              }
              icon="search"
              kind="filtered"
              title={
                query.search
                  ? "По этому запросу счетов нет"
                  : query.view === "archived"
                    ? "Архив пока пуст"
                    : "Активных счетов нет"
              }
            >
              {query.search
                ? "Измените запрос или очистите поиск."
                : "Счета появятся здесь после изменения их состояния."}
            </WorkbenchEmptyState>
          )}
        </WorkbenchSurface>
      </PageFrame>

      <ToastViewport onDismiss={dismissToast} toast={toast} />

      {createOpen ? (
        <AccountCreatePanel
          accountTypes={directory.accountTypes}
          csrfToken={session.csrfToken}
          defaultCurrency={session.workspace.defaultCurrency}
          onClose={() => setCreateOpen(false)}
          onCreated={commitCreated}
        />
      ) : null}

      {lifecycle.archiveCandidate ? (
        <ConfirmationDialog
          confirmLabel="Перенести в архив"
          description={`История и баланс счёта «${lifecycle.archiveCandidate.name}» сохранятся, но счёт нельзя будет выбирать для новых операций и импортов.`}
          onCancel={lifecycle.cancelArchive}
          onConfirm={lifecycle.confirmArchive}
          pending={lifecycle.pendingId === lifecycle.archiveCandidate.id}
          title="Перенести счёт в архив?"
        />
      ) : null}
    </AppShell>
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

function insertCommittedAccount(
  accounts: AccountSummaryDto[],
  account: AccountSummaryDto,
): AccountSummaryDto[] {
  const firstArchived = accounts.findIndex((item) => !item.isActive);
  if (firstArchived === -1) return [...accounts, account];
  return [
    ...accounts.slice(0, firstArchived),
    account,
    ...accounts.slice(firstArchived),
  ];
}
