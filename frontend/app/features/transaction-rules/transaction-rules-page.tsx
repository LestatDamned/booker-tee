import { type FormEvent, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { AppliedFilterSummary } from "../../ui/applied-filter-summary/applied-filter-summary";
import { Badge } from "../../ui/badge/badge";
import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../../ui/field/field";
import { FormActions } from "../../ui/field/form-layout";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import { ToastViewport } from "../../ui/toast/toast";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchFilterRegion } from "../../ui/workbench-content/workbench-filter-region";
import { WorkbenchStatus } from "../../ui/workbench-content/workbench-status";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchPagination } from "../../ui/workbench-pagination/workbench-pagination";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type { TransactionRuleDirectoryDto } from "./api/transaction-rules-api";
import { TransactionRuleCreatePanel } from "./transaction-rule-create-panel";
import { TransactionRuleLifecycleNotice } from "./transaction-rule-lifecycle-notice";
import {
  transactionRuleAppliedFilters,
  transactionRuleFilterUrl,
  transactionRuleListQuery,
  transactionRuleListSearch,
  transactionRulePageSizeUrl,
  transactionRulePageUrl,
  transactionRuleRangeLabel,
  transactionRuleSearchUrl,
  transactionRuleStatusUrl,
} from "./transaction-rule-list-query";
import {
  TransactionRuleMobileList,
  TransactionRuleTable,
} from "./transaction-rule-records";
import styles from "./transaction-rules-page.module.css";
import { useTransactionRuleMutations } from "./use-transaction-rule-mutations";
import { useTransactionRuleEditor } from "./use-transaction-rule-editor";
import { useTransactionRuleLifecycle } from "./use-transaction-rule-lifecycle";

export function TransactionRulesPage({
  directory,
  navigationPending = false,
  onReload,
  session,
}: {
  directory: TransactionRuleDirectoryDto;
  navigationPending?: boolean;
  onReload?: () => void;
  session: SessionDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const query = transactionRuleListQuery(location.search);
  const canonicalSearch = transactionRuleListSearch(query);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const createTriggerRef = useRef<HTMLButtonElement>(null);
  const seedTriggerRef = useRef<HTMLButtonElement>(null);
  const mutations = useTransactionRuleMutations({
    csrfToken: session.csrfToken,
    directory,
    navigate,
    ...(onReload ? { onReload } : {}),
    pathname: location.pathname,
  });
  const { snapshot } = mutations;
  const editor = useTransactionRuleEditor({
    csrfToken: session.csrfToken,
    onCommitted: mutations.ruleUpdated,
  });
  const lifecycle = useTransactionRuleLifecycle({
    csrfToken: session.csrfToken,
    onCommitted: mutations.ruleReplaced,
    showToast: mutations.showToast,
  });
  const [categoryDraft, setCategoryDraft] = useState(query.categoryId);
  const appliedFilters = transactionRuleAppliedFilters(snapshot);
  const targetId = ruleTargetId(location.hash);
  const targetFound =
    targetId === null || snapshot.items.some((rule) => rule.id === targetId);

  useEffect(() => {
    if (canonicalSearch === location.search) return;
    void navigate(
      {
        pathname: location.pathname,
        search: canonicalSearch,
        hash: location.hash,
      },
      { replace: true },
    );
  }, [
    canonicalSearch,
    location.hash,
    location.pathname,
    location.search,
    navigate,
  ]);

  useEffect(() => {
    if (!targetId || !targetFound) return;
    const records = Array.from(
      document.querySelectorAll<HTMLElement>(`[data-rule-id="${targetId}"]`),
    );
    const mobile = window.matchMedia?.("(max-width: 64rem)").matches ?? false;
    const target = mobile ? records.at(-1) : records[0];
    target?.scrollIntoView?.({ block: "center" });
    target?.focus({ preventScroll: true });
  }, [targetFound, targetId]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("q");
    void navigate(
      transactionRuleSearchUrl(
        location.search,
        typeof value === "string" ? value : "",
      ),
    );
  }

  function applyCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFiltersOpen(false);
    void navigate(transactionRuleFilterUrl(location.search, categoryDraft));
  }

  const resetSearch = transactionRuleListSearch({
    ...query,
    categoryId: "",
    page: 1,
    q: "",
  });

  return (
    <AppShell session={session}>
      <PageFrame className={styles.page} spacing="none">
        <PageHeader
          description="Условия, которые готовят предложения для Import Review, не обходя пользовательское подтверждение."
          eyebrow={ruleCountLabel(snapshot.counts.all)}
          title="Правила операций"
        />

        {snapshot.capabilities.readonlyReasonCode ? (
          <InlineNotice
            title="Правила доступны только для просмотра"
            tone="information"
          >
            Просматривать смысл правил можно с вашей ролью; изменение финансовых
            настроек недоступно.
          </InlineNotice>
        ) : null}

        {!targetFound ? (
          <InlineNotice
            title="Правило не найдено в текущей выборке"
            tone="warning"
          >
            Сбросьте фильтры или откройте страницу, на которой находится правило
            из ссылки.
          </InlineNotice>
        ) : null}

        {lifecycle.failure ? (
          <TransactionRuleLifecycleNotice
            failure={lifecycle.failure}
            onClear={lifecycle.clearFailure}
            onOpenEditor={editor.requestOpen}
            onRefreshAndRetry={() => void lifecycle.refreshAndRetry()}
            onRetry={lifecycle.retry}
            pending={lifecycle.pendingId !== null}
          />
        ) : null}

        <WorkbenchSurface
          aria-busy={navigationPending}
          aria-label="Реестр правил операций"
          className={styles.workbench}
        >
          <WorkbenchHeader>
            <div className={styles.registryHeading}>
              <span className={styles.registryTitle}>Каталог правил</span>
              {snapshot.capabilities.canSeedDefaults ? (
                <Button
                  ref={seedTriggerRef}
                  disabled={mutations.seedPending}
                  icon="rules"
                  onClick={mutations.openSeed}
                  tone="secondary"
                >
                  Базовые правила
                </Button>
              ) : null}
            </div>
          </WorkbenchHeader>
          <WorkbenchToolbar>
            <div className={styles.toolbarGrid}>
              <WorkbenchSearch
                ariaLabel="Поиск правил операций"
                inputId="transaction-rule-search"
                inputLabel="Поиск по названию, условию, категории, объекту или счёту"
                inputProps={{ defaultValue: query.q }}
                key={query.q}
                name="q"
                onSubmit={submitSearch}
                placeholder="Название, pattern, категория, объект или счёт"
              />
              <SelectionTabs
                as="nav"
                aria-label="Состояние правил"
                className={styles.statusTabs}
              >
                <SelectionTabLink
                  count={snapshot.counts.all}
                  selected={query.status === "all"}
                  to={transactionRuleStatusUrl(location.search, "all")}
                >
                  Все
                </SelectionTabLink>
                <SelectionTabLink
                  count={snapshot.counts.active}
                  selected={query.status === "active"}
                  to={transactionRuleStatusUrl(location.search, "active")}
                >
                  Активные
                </SelectionTabLink>
                <SelectionTabLink
                  count={snapshot.counts.disabled}
                  selected={query.status === "disabled"}
                  to={transactionRuleStatusUrl(location.search, "disabled")}
                >
                  Выключенные
                </SelectionTabLink>
              </SelectionTabs>
              <Button
                aria-controls="transaction-rule-filter-region"
                aria-expanded={filtersOpen}
                icon="filter"
                onClick={() => setFiltersOpen((current) => !current)}
              >
                Фильтры
                {query.categoryId ? <Badge>1</Badge> : null}
              </Button>
              {snapshot.capabilities.canCreate ? (
                <Button
                  ref={createTriggerRef}
                  aria-haspopup="dialog"
                  icon="plus"
                  onClick={mutations.openCreate}
                  tone="primary"
                >
                  Новое правило
                </Button>
              ) : null}
            </div>
            <AppliedFilterSummary
              filters={filtersOpen ? [] : appliedFilters}
              resetTo={resetSearch || location.pathname}
            />
          </WorkbenchToolbar>

          {filtersOpen ? (
            <WorkbenchFilterRegion id="transaction-rule-filter-region">
              <form className={styles.filterForm} onSubmit={applyCategory}>
                <Field
                  htmlFor="transaction-rule-category"
                  label="Категория результата"
                >
                  <select
                    id="transaction-rule-category"
                    onChange={(event) =>
                      setCategoryDraft(event.currentTarget.value)
                    }
                    value={categoryDraft}
                  >
                    <option value="">Все категории</option>
                    {snapshot.references.categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                        {category.isActive ? "" : " · архив"}
                      </option>
                    ))}
                  </select>
                </Field>
                <FormActions layout="split">
                  <Button onClick={() => setCategoryDraft("")} type="button">
                    Очистить
                  </Button>
                  <Button icon="filterApply" tone="primary" type="submit">
                    Применить
                  </Button>
                </FormActions>
              </form>
            </WorkbenchFilterRegion>
          ) : null}

          <WorkbenchStatus>
            {navigationPending ? "Обновляем правила…" : ""}
          </WorkbenchStatus>
          <WorkbenchContent
            aria-label="Правила операций"
            isEmpty={snapshot.items.length === 0}
          >
            {snapshot.items.length === 0 ? (
              <WorkbenchEmptyState
                icon={appliedFilters.length ? "search" : "rules"}
                kind={appliedFilters.length ? "filtered" : "primary"}
                title={
                  appliedFilters.length
                    ? "По этим условиям правил нет"
                    : "Правил пока нет"
                }
              >
                {appliedFilters.length
                  ? "Измените поиск или категорию результата."
                  : "Создайте первое правило или добавьте недостающий базовый набор."}
              </WorkbenchEmptyState>
            ) : (
              <ResponsiveRecordCollection
                mobileList={
                  <TransactionRuleMobileList
                    editPanel={editor.panel}
                    editingRuleId={editor.opened?.ruleId ?? null}
                    editingVariant={editor.opened?.variant ?? null}
                    onEdit={editor.requestOpen}
                    lifecyclePendingId={lifecycle.pendingId}
                    onDisable={lifecycle.disable}
                    onEnable={lifecycle.enable}
                    onEnableBlocked={lifecycle.explainBlocked}
                    rules={snapshot.items}
                    targetId={targetId}
                  />
                }
                table={
                  <TransactionRuleTable
                    editPanel={editor.panel}
                    editingRuleId={editor.opened?.ruleId ?? null}
                    editingVariant={editor.opened?.variant ?? null}
                    onEdit={editor.requestOpen}
                    lifecyclePendingId={lifecycle.pendingId}
                    onDisable={lifecycle.disable}
                    onEnable={lifecycle.enable}
                    onEnableBlocked={lifecycle.explainBlocked}
                    rules={snapshot.items}
                    targetId={targetId}
                  />
                }
              />
            )}
          </WorkbenchContent>
          <WorkbenchPagination
            ariaLabel="Страницы правил"
            currentPage={snapshot.page.page}
            getPageHref={(page) =>
              transactionRulePageUrl(location.search, page)
            }
            hasNext={snapshot.page.hasNext}
            hasPrevious={snapshot.page.hasPrevious}
            pageSize={{
              disabled: navigationPending,
              id: "transaction-rule-page-size",
              onChange: (pageSize) =>
                void navigate(
                  transactionRulePageSizeUrl(location.search, pageSize),
                ),
              options: [25, 50, 100],
              value: snapshot.page.pageSize,
            }}
            summary={transactionRuleRangeLabel(
              snapshot.page.page,
              snapshot.page.pageSize,
              snapshot.page.total,
            )}
            totalPages={snapshot.page.totalPages}
          />
        </WorkbenchSurface>
        {mutations.createOpen ? (
          <TransactionRuleCreatePanel
            csrfToken={session.csrfToken}
            onClose={mutations.closeCreate}
            onCreated={mutations.ruleCreated}
            references={snapshot.references}
          />
        ) : null}
        {mutations.seedConfirmOpen ? (
          <ConfirmationDialog
            confirmLabel="Добавить недостающие"
            confirmTone="primary"
            description="Будут созданы только отсутствующие базовые категории и правила. Существующие правила, режимы и состояния не изменятся."
            disabled={mutations.seedPending}
            onCancel={mutations.closeSeed}
            onConfirm={() => void mutations.seedDefaults()}
            pending={mutations.seedPending}
            returnFocusRef={seedTriggerRef}
            title="Добавить базовые правила?"
          >
            {mutations.seedError ? (
              <InlineNotice title="Не удалось добавить правила" tone="danger">
                {mutations.seedError}
              </InlineNotice>
            ) : null}
          </ConfirmationDialog>
        ) : null}
        {editor.dialog}
        <ToastViewport
          onDismiss={mutations.dismissToast}
          toast={mutations.toast}
        />
      </PageFrame>
    </AppShell>
  );
}

function ruleTargetId(hash: string): string | null {
  const match = /^#rule-([0-9a-f-]{36})$/i.exec(hash);
  return match?.[1] ?? null;
}

function ruleCountLabel(count: number): string {
  const lastTwo = count % 100;
  const last = count % 10;
  const word =
    lastTwo >= 11 && lastTwo <= 14
      ? "правил"
      : last === 1
        ? "правило"
        : last >= 2 && last <= 4
          ? "правила"
          : "правил";
  return `${count} ${word}`;
}
