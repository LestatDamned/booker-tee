import { useState, type FormEvent } from "react";

import type { SessionDto } from "../../api/session";
import { loginHref } from "../../session/unauthenticated";
import { Button, ButtonLink } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import {
  acceptPublicWorkspaceInvitation,
  type PublicWorkspaceInvitationDto,
} from "./api/workspace-invitations-api";
import { workspaceRoleLabel } from "./workspace-labels";
import styles from "./workspace-invitation-page.module.css";

export function WorkspaceInvitationPage({
  invitation,
  invitationToken,
  navigate = (href) => window.location.assign(href),
  session,
}: {
  invitation: PublicWorkspaceInvitationDto;
  invitationToken: string;
  navigate?: (href: string) => void;
  session: SessionDto | null;
}) {
  const returnTo = `/app/workspaces/invitations/${encodeURIComponent(invitationToken)}`;
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  async function accept(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || pending || unavailable) return;
    setPending(true);
    setError(null);
    const result = await acceptPublicWorkspaceInvitation({
      csrfToken: session.csrfToken,
      invitationToken,
    });
    setPending(false);
    if (result.status === "success") {
      navigate(result.href);
      return;
    }
    if (result.status === "unauthenticated") {
      navigate(loginHref(returnTo));
      return;
    }
    if (result.status === "not_found") setUnavailable(true);
    setError(result.message);
  }

  return (
    <main className={styles.page}>
      <section aria-labelledby="invitation-title" className={styles.card}>
        <a className={styles.brand} href="/app">
          Booker Tee
        </a>
        <header className={styles.heading}>
          <h1 id="invitation-title">Приглашение</h1>
          <p>Вас приглашают в рабочее пространство.</p>
        </header>

        <dl className={styles.details}>
          <div>
            <dt>Пространство</dt>
            <dd>{invitation.workspaceName}</dd>
          </div>
          <div>
            <dt>Роль</dt>
            <dd>{workspaceRoleLabel(invitation.role)}</dd>
          </div>
          <div>
            <dt>Действует до</dt>
            <dd>{formatDateTime(invitation.expiresAt)}</dd>
          </div>
        </dl>

        {error ? (
          <InlineNotice
            role="alert"
            title="Приглашение не принято"
            tone="danger"
          >
            {error}
          </InlineNotice>
        ) : null}

        {session ? (
          <form
            className={styles.actions}
            onSubmit={(event) => void accept(event)}
          >
            <InlineNotice tone="information">
              Вы войдёте как {session.user.email}.
            </InlineNotice>
            <Button
              disabled={unavailable}
              icon="check"
              isLoading={pending}
              tone="primary"
              type="submit"
            >
              {pending ? "Принимаем…" : "Принять приглашение"}
            </Button>
            <ButtonLink href="/app/workspaces" tone="ghost">
              Рабочие пространства
            </ButtonLink>
          </form>
        ) : (
          <div className={styles.actions}>
            <InlineNotice tone="information">
              Сначала войдите или создайте аккаунт. После этого вы вернётесь к
              приглашению.
            </InlineNotice>
            <ButtonLink href={loginHref(returnTo)} tone="primary">
              Войти
            </ButtonLink>
            <ButtonLink
              href={`/app/auth/signup?next=${encodeURIComponent(returnTo)}`}
              tone="secondary"
            >
              Создать аккаунт
            </ButtonLink>
          </div>
        )}
      </section>
    </main>
  );
}

const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDateTime(value: string) {
  return dateTimeFormatter.format(new Date(value));
}
