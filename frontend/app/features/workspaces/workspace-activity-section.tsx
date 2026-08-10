import { useEffect, useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import {
  loadWorkspaceActivity,
  type WorkspaceActivityDto,
  type WorkspaceActivityItemDto,
  type WorkspaceActivityLoadResult,
} from "./api/workspace-activity-api";
import { workspaceRoleLabel } from "./workspace-labels";
import styles from "./workspace-settings-page.module.css";

export function WorkspaceActivitySection({
  initialResult,
  refreshToken = 0,
  workspaceId,
}: {
  initialResult: WorkspaceActivityLoadResult;
  refreshToken?: number;
  workspaceId: string;
}) {
  const lastRefreshToken = useRef(refreshToken);
  const [activity, setActivity] = useState<WorkspaceActivityDto | null>(
    initialResult.status === "success" ? initialResult.activity : null,
  );
  const [error, setError] = useState(
    initialResult.status === "error" ||
      initialResult.status === "forbidden" ||
      initialResult.status === "not_found"
      ? initialResult.message
      : null,
  );
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (lastRefreshToken.current === refreshToken) return;
    lastRefreshToken.current = refreshToken;
    let cancelled = false;
    setPending(true);
    setError(null);
    void loadWorkspaceActivity(workspaceId).then((result) => {
      if (cancelled) return;
      setPending(false);
      if (result.status === "success") {
        setActivity(result.activity);
      } else if (result.status === "unauthenticated") {
        window.location.assign("/app/auth/login");
      } else {
        setError(result.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [refreshToken, workspaceId]);

  async function loadMore() {
    if (pending) return;
    const cursor = activity?.nextCursor ?? undefined;
    setPending(true);
    setError(null);
    const result = await loadWorkspaceActivity(workspaceId, cursor);
    setPending(false);
    if (result.status === "success") {
      setActivity({
        ...result.activity,
        items:
          activity && cursor
            ? [...activity.items, ...result.activity.items]
            : result.activity.items,
      });
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/app/auth/login");
      return;
    }
    setError(result.message);
  }

  return (
    <section
      aria-labelledby="workspace-activity-title"
      className={styles.section}
    >
      <div className={styles.sectionHeading}>
        <div>
          <h2 id="workspace-activity-title">Активность</h2>
          <p>Изменения доступа, участников и настроек пространства.</p>
        </div>
      </div>

      {error ? (
        <InlineNotice
          action={
            <Button onClick={() => void loadMore()} tone="secondary">
              Повторить
            </Button>
          }
          role="alert"
          title="Не удалось загрузить активность"
          tone="warning"
        >
          {error}
        </InlineNotice>
      ) : null}

      {activity?.items.length ? (
        <ol className={styles.activityList}>
          {activity.items.map((item) => (
            <li className={styles.activityItem} key={item.id}>
              <span aria-hidden="true" className={styles.activityMarker} />
              <div>
                <p>{activitySummary(item)}</p>
                <time dateTime={item.createdAt}>
                  {formatDateTime(item.createdAt)}
                </time>
              </div>
            </li>
          ))}
        </ol>
      ) : error ? null : (
        <p className={styles.invitationEmpty}>Изменений пока нет.</p>
      )}

      {activity?.nextCursor ? (
        <div className={styles.activityActions}>
          <Button
            isLoading={pending}
            onClick={() => void loadMore()}
            tone="secondary"
          >
            Показать ещё
          </Button>
        </div>
      ) : null}
    </section>
  );
}

function activitySummary(item: WorkspaceActivityItemDto): string {
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
