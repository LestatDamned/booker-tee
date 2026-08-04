import { useState } from "react";
import { Link } from "react-router";

import { loadSession } from "../api/session";
import {
  loadUserSessions,
  logout,
  revokeOtherUserSessions,
  revokeUserSession,
  type UserSessionDto,
} from "../features/users/api/account-api";
import styles from "../features/users/profile/session-page.module.css";
import { AppShell } from "../shell/app-shell";
import { AuthenticatedRouteStatePage } from "../session/authenticated-route-state-page";
import { redirectIfUnauthenticated } from "../session/unauthenticated";
import { Button } from "../ui/button/button";
import { ConfirmationDialog } from "../ui/confirmation-dialog/confirmation-dialog";
import { InlineNotice } from "../ui/inline-notice/inline-notice";
import { PageFrame } from "../ui/page-frame/page-frame";
import { PageHeader } from "../ui/page-header/page-header";
import { StatusLabel } from "../ui/status-label/status-label";
import { ToastViewport, useToastQueue } from "../ui/toast/toast";
import { WorkbenchEmptyState } from "../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchSurface } from "../ui/workbench-surface/workbench-surface";
import type { Route } from "./+types/profile-sessions";

export function meta() {
  return [{ title: "Активные сессии — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const [session, sessions] = await Promise.all([
    loadSession(request.signal),
    loadUserSessions(request.signal),
  ]);
  return { session, sessions };
}

type ConfirmationTarget =
  | { kind: "current" }
  | { kind: "one"; session: UserSessionDto }
  | { kind: "others" };

export default function ProfileSessionsRoute({
  loaderData,
}: Route.ComponentProps) {
  if (loaderData.session.status === "loading") {
    return <SessionRouteError message="Сессия ещё не загружена." />;
  }
  if (loaderData.session.status !== "authenticated") {
    return (
      <AuthenticatedRouteStatePage
        errorTitle="Не удалось загрузить активные сессии"
        result={loaderData.session}
        returnTo="/app/profile/sessions"
      />
    );
  }
  if (loaderData.sessions.status !== "success") {
    return (
      <AuthenticatedRouteStatePage
        errorTitle="Не удалось загрузить активные сессии"
        result={loaderData.sessions}
        returnTo="/app/profile/sessions"
      />
    );
  }
  return (
    <AppShell session={loaderData.session.session}>
      <SessionsPage
        csrfToken={loaderData.session.session.csrfToken}
        initialSessions={loaderData.sessions.sessions}
      />
    </AppShell>
  );
}

export function SessionsPage({
  csrfToken,
  initialSessions,
}: {
  csrfToken: string;
  initialSessions: UserSessionDto[];
}) {
  const [sessions, setSessions] = useState(initialSessions);
  const [confirmation, setConfirmation] = useState<ConfirmationTarget | null>(
    null,
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { dismissToast, showToast, toast } = useToastQueue();
  const otherSessions = sessions.filter((item) => !item.isCurrent);

  async function confirmAction() {
    if (!confirmation) return;
    setPending(true);
    setError(null);
    if (confirmation.kind === "current") {
      const result = await logout(csrfToken);
      if (result.status === "success" || result.status === "unauthenticated") {
        window.location.assign("/app/auth/login");
        return;
      }
      setError(result.message ?? "Не удалось выйти.");
      setPending(false);
      setConfirmation(null);
      return;
    }

    const result =
      confirmation.kind === "others"
        ? await revokeOtherUserSessions(csrfToken)
        : await revokeUserSession(confirmation.session.id, csrfToken);
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "error") {
      setError(result.message);
      setPending(false);
      setConfirmation(null);
      return;
    }
    const refreshed = await loadUserSessions();
    if (redirectIfUnauthenticated(refreshed)) return;
    if (refreshed.status === "success") {
      setSessions(refreshed.sessions);
      showToast({
        message:
          confirmation.kind === "others"
            ? "Остальные сессии завершены."
            : "Сессия завершена.",
      });
    } else {
      setError(refreshed.message);
    }
    setPending(false);
    setConfirmation(null);
  }

  return (
    <PageFrame aria-labelledby="sessions-title">
      <div className={styles.content}>
        <Link to="/profile/security">← Безопасность</Link>
        <PageHeader
          actions={
            otherSessions.length > 0 ? (
              <Button
                onClick={() => setConfirmation({ kind: "others" })}
                tone="dangerSecondary"
              >
                Завершить остальные
              </Button>
            ) : null
          }
          description="Проверяйте устройства, на которых открыт ваш аккаунт. Геолокация и IP не сохраняются."
          eyebrow="Аккаунт"
          title="Активные сессии"
          titleId="sessions-title"
        />
        {error ? (
          <InlineNotice aria-live="polite" tone="danger">
            {error}
          </InlineNotice>
        ) : null}
        <WorkbenchSurface>
          {sessions.length === 0 ? (
            <WorkbenchEmptyState
              icon="neutral"
              title="Активные сессии не найдены"
            >
              Обновите страницу. Если сессия истекла, Booker Tee предложит войти
              снова.
            </WorkbenchEmptyState>
          ) : (
            <ul aria-label="Активные сессии" className={styles.list}>
              {sessions.map((item) => (
                <li className={styles.item} key={item.id}>
                  <div className={styles.identity}>
                    <div className={styles.titleRow}>
                      <h2>{item.deviceSummary}</h2>
                      {item.isCurrent ? (
                        <StatusLabel tone="success" variant="soft">
                          Текущая
                        </StatusLabel>
                      ) : null}
                    </div>
                    <dl className={styles.facts}>
                      <div>
                        <dt>Последняя активность</dt>
                        <dd>{formatDateTime(item.lastSeenAt)}</dd>
                      </div>
                      <div>
                        <dt>Создана</dt>
                        <dd>{formatDateTime(item.createdAt)}</dd>
                      </div>
                      <div>
                        <dt>Действует до</dt>
                        <dd>{formatDateTime(item.expiresAt)}</dd>
                      </div>
                    </dl>
                  </div>
                  <Button
                    onClick={() =>
                      setConfirmation(
                        item.isCurrent
                          ? { kind: "current" }
                          : { kind: "one", session: item },
                      )
                    }
                    tone="dangerSecondary"
                  >
                    {item.isCurrent ? "Выйти" : "Завершить"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </WorkbenchSurface>
      </div>
      {confirmation ? (
        <ConfirmationDialog
          confirmLabel={confirmation.kind === "current" ? "Выйти" : "Завершить"}
          description={confirmationDescription(confirmation)}
          onCancel={() => setConfirmation(null)}
          onConfirm={confirmAction}
          pending={pending}
          title={
            confirmation.kind === "current"
              ? "Выйти из аккаунта?"
              : "Завершить сессии?"
          }
        />
      ) : null}
      <ToastViewport onDismiss={dismissToast} toast={toast} />
    </PageFrame>
  );
}

function SessionRouteError({ message }: { message: string }) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить активные сессии"
      result={{ status: "error", message }}
      returnTo="/app/profile/sessions"
    />
  );
}

function confirmationDescription(target: ConfirmationTarget): string {
  if (target.kind === "current") {
    return "Текущая серверная сессия будет отозвана. Для продолжения потребуется войти снова.";
  }
  if (target.kind === "others") {
    return "Все активные сессии, кроме текущей, будут завершены.";
  }
  return `Сессия «${target.session.deviceSummary}» будет завершена.`;
}

const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Неизвестно"
    : dateTimeFormatter.format(date);
}
