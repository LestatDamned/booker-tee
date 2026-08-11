import { useState } from "react";
import { Link } from "react-router";

import type { SessionDto } from "../../api/session";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { AppShell } from "../../shell/app-shell";
import { BackLink } from "../../ui/back-link/back-link";
import { Button } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { Tag } from "../../ui/tag/tag";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import {
  loadWorkspaceActivity,
  type WorkspaceActivityDto,
  type WorkspaceActivityItemDto,
  type WorkspaceActivityScope,
} from "./api/workspace-activity-api";
import { workspaceRoleLabel } from "./workspace-labels";
import styles from "./workspace-activity-page.module.css";

export function WorkspaceActivityPage({
  initialActivity,
  navigationPending = false,
  scope,
  session,
}: {
  initialActivity: WorkspaceActivityDto;
  navigationPending?: boolean;
  scope: WorkspaceActivityScope;
  session: SessionDto;
}) {
  const [localActivity, setLocalActivity] = useState<{
    source: WorkspaceActivityDto;
    value: WorkspaceActivityDto;
  } | null>(null);
  const [localError, setLocalError] = useState<{
    source: WorkspaceActivityDto;
    message: string;
  } | null>(null);
  const [pending, setPending] = useState(false);
  const activity =
    localActivity?.source === initialActivity
      ? localActivity.value
      : initialActivity;
  const error =
    localError?.source === initialActivity ? localError.message : null;

  async function loadMore() {
    if (pending || !activity.nextCursor) return;
    setPending(true);
    setLocalError(null);
    const result = await loadWorkspaceActivity(
      activity.workspaceId,
      activity.nextCursor,
    );
    setPending(false);
    if (result.status === "success") {
      setLocalActivity({
        source: initialActivity,
        value: {
          ...result.activity,
          items: [...activity.items, ...result.activity.items],
        },
      });
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setLocalError({ source: initialActivity, message: result.message });
  }

  return (
    <AppShell session={session}>
      <PageFrame mobileTop="compact" spacing="block">
        <WorkbenchSurface
          aria-busy={navigationPending || pending}
          className={styles.workbench}
        >
          <WorkbenchHeader>
            <BackLink to={`/workspaces/${activity.workspaceId}/settings`}>
              Настройки пространства
            </BackLink>
            <PageHeader
              description="Кто и когда менял финансы, команду и настройки пространства."
              eyebrow="Рабочее пространство"
              title="История действий"
            />
          </WorkbenchHeader>

          <WorkbenchToolbar aria-label="Фильтр истории действий">
            <SelectionTabs as="nav" aria-label="Раздел истории">
              <SelectionTabLink selected={scope === "all"} to="?scope=all">
                Все
              </SelectionTabLink>
              <SelectionTabLink
                selected={scope === "finance"}
                to="?scope=finance"
              >
                Финансы
              </SelectionTabLink>
              <SelectionTabLink selected={scope === "team"} to="?scope=team">
                Команда
              </SelectionTabLink>
            </SelectionTabs>
          </WorkbenchToolbar>

          {error ? (
            <InlineNotice
              action={
                <Button
                  isLoading={pending}
                  onClick={() => void loadMore()}
                  tone="secondary"
                >
                  Повторить
                </Button>
              }
              className={styles.notice}
              role="alert"
              title="Не удалось загрузить продолжение"
              tone="warning"
            >
              {error}
            </InlineNotice>
          ) : null}

          <WorkbenchContent
            aria-label="События рабочего пространства"
            className={styles.content}
            isEmpty={activity.items.length === 0}
          >
            {activity.items.length ? (
              <ol className={styles.timeline}>
                {activity.items.map((item) => (
                  <ActivityItem item={item} key={item.id} />
                ))}
              </ol>
            ) : (
              <WorkbenchEmptyState
                icon="information"
                title={scope === "all" ? "Истории пока нет" : "Событий нет"}
              >
                {scope === "all"
                  ? "Значимые действия появятся здесь после изменений в пространстве."
                  : "В выбранном разделе пока не было значимых действий."}
              </WorkbenchEmptyState>
            )}

            {activity.nextCursor ? (
              <div className={styles.pagination}>
                <Button
                  isLoading={pending}
                  onClick={() => void loadMore()}
                  tone="secondary"
                >
                  Показать ещё
                </Button>
              </div>
            ) : null}
          </WorkbenchContent>
        </WorkbenchSurface>
      </PageFrame>
    </AppShell>
  );
}

function ActivityItem({ item }: { item: WorkspaceActivityItemDto }) {
  const href = entityHref(item);
  const label = entityLabel(item);
  return (
    <li className={styles.item} data-scope={item.scope}>
      <span aria-hidden="true" className={styles.marker} />
      <article className={styles.event}>
        <p className={styles.summary}>{activitySummary(item)}</p>
        <div className={styles.meta}>
          <time dateTime={item.createdAt}>
            {formatDateTime(item.createdAt)}
          </time>
          <Tag tone={item.scope === "finance" ? "adjustment" : "neutral"}>
            {item.scope === "finance" ? "Финансы" : "Команда"}
          </Tag>
          {label && href ? <Link to={href}>{label}</Link> : null}
          {label && !href ? (
            <span>
              {label}
              {item.entity && !item.entity.isAvailable ? " · недоступно" : ""}
            </span>
          ) : null}
        </div>
      </article>
    </li>
  );
}

function entityHref(item: WorkspaceActivityItemDto): string | null {
  const entity = item.entity;
  if (!entity?.isAvailable) return null;
  switch (entity.type) {
    case "workspace":
      return `/workspaces/${entity.id}/settings`;
    case "debt":
      return `/debts/${entity.id}`;
    case "uploaded_document":
      return `/imports/documents/${entity.id}`;
    case "operation":
      return null;
  }
}

function entityLabel(item: WorkspaceActivityItemDto): string | null {
  if (!item.entity) return null;
  if (item.entity.displayLabel) return item.entity.displayLabel;
  switch (item.entity.type) {
    case "workspace":
      return "Настройки пространства";
    case "operation":
      return "Операция";
    case "debt":
      return "Долг";
    case "uploaded_document":
      return "Документ импорта";
  }
}

export function activitySummary(item: WorkspaceActivityItemDto): string {
  const actor = item.actor?.displayName ?? "Система";
  const target = item.target?.displayName ?? "участника";
  const details = item.details;
  switch (item.summaryCode) {
    case "workspace_created":
      return `${actor} создал пространство`;
    case "workspace_updated":
      return `${actor} изменил настройки пространства`;
    case "workspace_deactivated":
      return `${actor} деактивировал пространство`;
    case "workspace_restored":
      return `${actor} восстановил пространство`;
    case "invitation_created":
      return `${actor} пригласил ${details.inviteeEmail ?? "участника"}${roleSuffix(details.role)}`;
    case "invitation_accepted":
      return `${actor} принял приглашение${roleSuffix(details.role)}`;
    case "invitation_revoked":
      return `${actor} отозвал приглашение для ${details.inviteeEmail ?? "участника"}`;
    case "member_role_changed":
      return `${actor} изменил роль ${target}: ${role(details.oldRole)} → ${role(details.newRole)}`;
    case "member_disabled":
      return `${actor} отключил доступ ${target}`;
    case "member_reactivated":
      return `${actor} восстановил доступ ${target}`;
    case "member_left":
      return `${actor} покинул пространство`;
    case "ownership_transferred":
      return `${actor} передал владение пользователю ${target}`;
    case "manual_operation_created":
      return `${actor} создал операцию «${details.displayLabel ?? "Без описания"}»`;
    case "manual_operation_updated":
      return `${actor} изменил операцию «${details.displayLabel ?? "Без описания"}»`;
    case "manual_operation_cancelled":
      return `${actor} отменил операцию «${details.displayLabel ?? "Без описания"}»`;
    case "manual_operation_restored":
      return `${actor} восстановил операцию «${details.displayLabel ?? "Без описания"}»`;
    case "manual_operation_deleted":
      return `${actor} удалил операцию «${details.displayLabel ?? "Без описания"}»`;
    case "import_review_item_confirmed":
      return `${actor} подтвердил операцию из импорта`;
    case "import_review_transfer_created":
      return `${actor} создал перевод из импорта`;
    case "import_review_operation_linked":
      return `${actor} связал строку импорта с операцией`;
    case "import_review_posting_undone":
      return `${actor} отменил проведение импортированной операции`;
    case "import_review_operation_unlinked":
      return `${actor} отвязал строку импорта от операции`;
    case "imported_operation_updated":
      return `${actor} изменил импортированную операцию`;
    case "debt_created":
      return `${actor} добавил долг «${details.displayLabel ?? "Без названия"}»`;
    case "debt_payment_recorded":
      return `${actor} записал платёж по долгу`;
    case "debt_payment_undone":
      return `${actor} отменил платёж по долгу`;
    case "debt_updated":
      return `${actor} изменил долг «${details.displayLabel ?? "Без названия"}»`;
    case "debt_archived":
      return `${actor} архивировал долг`;
    case "debt_restored":
      return `${actor} восстановил долг`;
    case "debt_deleted":
      return `${actor} удалил долг «${details.displayLabel ?? "Без названия"}»`;
    case "document_uploaded":
      return `${actor} загрузил документ «${details.displayFilename ?? "Без названия"}»`;
  }
}

function role(value: WorkspaceActivityItemDto["details"]["role"]): string {
  return value ? workspaceRoleLabel(value) : "неизвестно";
}

function roleSuffix(
  value: WorkspaceActivityItemDto["details"]["role"],
): string {
  return value ? ` с ролью «${workspaceRoleLabel(value)}»` : "";
}

const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDateTime(value: string): string {
  return dateTimeFormatter.format(new Date(value));
}
