import { useRef, useState, type FormEvent } from "react";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { StatusLabel } from "../../ui/status-label/status-label";
import {
  createWorkspaceInvitation,
  loadWorkspaceInvitations,
  revokeWorkspaceInvitation,
  type WorkspaceInvitationDto,
  type WorkspaceInvitationsDto,
} from "./api/workspace-invitations-api";
import { workspaceRoleLabel } from "./workspace-labels";
import styles from "./workspace-settings-page.module.css";

export function WorkspaceInvitationsSection({
  csrfToken,
  initialInvitations,
}: {
  csrfToken: string;
  initialInvitations: WorkspaceInvitationsDto;
}) {
  const idempotencyKey = useRef(crypto.randomUUID());
  const [invitations, setInvitations] = useState(initialInvitations);
  const [role, setRole] = useState(
    initialInvitations.capabilities.assignableRoles[0] ?? "viewer",
  );
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [revokeTarget, setRevokeTarget] =
    useState<WorkspaceInvitationDto | null>(null);
  const [notice, setNotice] = useState<{
    message: string;
    tone: "danger" | "warning";
  } | null>(null);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !invitations.capabilities.canCreate) return;
    setPending(true);
    setNotice(null);
    const result = await createWorkspaceInvitation({
      csrfToken,
      idempotencyKey: idempotencyKey.current,
      role,
      workspaceId: invitations.workspaceId,
    });
    setPending(false);
    if (result.status === "success") {
      setInvitations(result.invitations);
      setShareUrl(result.shareUrl);
      idempotencyKey.current = crypto.randomUUID();
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setNotice({ message: result.message, tone: "danger" });
  }

  async function revoke() {
    if (!revokeTarget || pending) return;
    setPending(true);
    setNotice(null);
    const result = await revokeWorkspaceInvitation({
      csrfToken,
      invitation: revokeTarget,
      workspaceId: invitations.workspaceId,
    });
    setPending(false);
    setRevokeTarget(null);
    if (result.status === "success") {
      setInvitations(result.invitations);
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "conflict" || result.status === "not_found") {
      const fresh = await loadWorkspaceInvitations(invitations.workspaceId);
      if (fresh.status === "success") setInvitations(fresh.invitations);
      setNotice({
        message: `${result.message} Список приглашений обновлён.`,
        tone: "warning",
      });
      return;
    }
    setNotice({ message: result.message, tone: "danger" });
  }

  async function copyShareUrl() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
    } catch {
      setNotice({
        message:
          "Не удалось скопировать ссылку. Выделите её и скопируйте вручную.",
        tone: "warning",
      });
    }
  }

  return (
    <section
      aria-labelledby="workspace-invitations-title"
      className={styles.section}
    >
      <div className={styles.sectionHeading}>
        <div>
          <h2 id="workspace-invitations-title">Приглашения</h2>
          <p>Ссылка даёт выбранную роль и действует 72 часа.</p>
        </div>
        <span className={styles.memberCount}>{invitations.items.length}</span>
      </div>

      {notice ? (
        <InlineNotice
          role="status"
          title="Приглашения не изменены"
          tone={notice.tone}
        >
          {notice.message}
        </InlineNotice>
      ) : null}

      {invitations.capabilities.canCreate ? (
        <form
          className={styles.invitationForm}
          onSubmit={(event) => void create(event)}
        >
          <label>
            <span>Роль</span>
            <select
              disabled={pending}
              onChange={(event) =>
                setRole(event.target.value as WorkspaceInvitationDto["role"])
              }
              value={role}
            >
              {invitations.capabilities.assignableRoles.map((option) => (
                <option key={option} value={option}>
                  {workspaceRoleLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <Button isLoading={pending} tone="primary" type="submit">
            Создать ссылку
          </Button>
        </form>
      ) : (
        <StatusLabel tone="neutral">Создание недоступно</StatusLabel>
      )}

      {shareUrl ? (
        <InlineNotice
          action={
            <div className={styles.invitationShareActions}>
              <Button onClick={() => void copyShareUrl()} tone="secondary">
                Скопировать
              </Button>
              <Button onClick={() => setShareUrl(null)} tone="ghost">
                Закрыть
              </Button>
            </div>
          }
          role="status"
          title="Ссылка готова"
          tone="success"
        >
          <label className={styles.invitationShareField}>
            <span>Ссылка приглашения</span>
            <input readOnly value={shareUrl} />
          </label>
          <span>
            После закрытия эта ссылка больше не показывается в настройках.
          </span>
        </InlineNotice>
      ) : null}

      {invitations.items.length ? (
        <div
          aria-label="Ожидающие приглашения"
          className={styles.invitationList}
          role="list"
        >
          {invitations.items.map((invitation) => (
            <article
              className={styles.invitationRow}
              key={invitation.id}
              role="listitem"
            >
              <div>
                <strong>{workspaceRoleLabel(invitation.role)}</strong>
                <span>
                  Создано {formatDateTime(invitation.createdAt)} · до{" "}
                  {formatDateTime(invitation.expiresAt)}
                </span>
              </div>
              <StatusLabel tone="warning">Ожидает</StatusLabel>
              {invitation.capabilities.canRevoke ? (
                <Button
                  disabled={pending}
                  onClick={() => setRevokeTarget(invitation)}
                  tone="dangerSecondary"
                >
                  Отозвать
                </Button>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className={styles.invitationEmpty}>Ожидающих приглашений нет.</p>
      )}

      {revokeTarget ? (
        <ConfirmationDialog
          confirmLabel="Отозвать приглашение"
          description={`Ссылка с ролью «${workspaceRoleLabel(revokeTarget.role)}» перестанет работать. Уже принятый доступ это не изменит.`}
          onCancel={() => setRevokeTarget(null)}
          onConfirm={() => void revoke()}
          pending={pending}
          title="Отозвать приглашение?"
        />
      ) : null}
    </section>
  );
}

const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDateTime(value: string) {
  return dateTimeFormatter.format(new Date(value));
}
