import { useState } from "react";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { StatusLabel } from "../../ui/status-label/status-label";
import {
  loadWorkspaceMembers,
  leaveWorkspace,
  transitionWorkspaceMember,
  transferWorkspaceOwnership,
  updateWorkspaceMemberRole,
  type WorkspaceMemberDto,
  type WorkspaceMembersDto,
} from "./api/workspace-members-api";
import {
  workspaceRoleLabel,
  workspaceRoleOptionLabel,
} from "./workspace-labels";
import styles from "./workspace-settings-page.module.css";

export function WorkspaceMembersSection({
  boundaryNavigate,
  csrfToken,
  currentWorkspaceId,
  initialMembers,
  onCommittedMutation,
  workspaceUpdatedAt,
}: {
  boundaryNavigate: (href: string, message?: string) => void;
  csrfToken: string;
  currentWorkspaceId: string;
  initialMembers: WorkspaceMembersDto;
  onCommittedMutation?: () => void;
  workspaceUpdatedAt: string;
}) {
  const [members, setMembers] = useState(initialMembers);
  const [pendingMemberId, setPendingMemberId] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<{
    kind: "disable" | "leave" | "transfer";
    member: WorkspaceMemberDto;
  } | null>(null);
  const [notice, setNotice] = useState<{
    message: string;
    tone: "danger" | "warning";
  } | null>(null);

  async function changeRole(
    member: WorkspaceMemberDto,
    role: WorkspaceMemberDto["role"],
  ) {
    if (role === member.role || pendingMemberId) return;
    setPendingMemberId(member.id);
    setNotice(null);
    const result = await updateWorkspaceMemberRole({
      csrfToken,
      member,
      role,
      workspaceId: members.workspaceId,
    });
    setPendingMemberId(null);
    await receiveMutation(result);
  }

  async function confirmDisable() {
    if (!confirmation || pendingMemberId) return;
    const member = confirmation.member;
    setPendingMemberId(member.id);
    setNotice(null);
    const result = await transitionWorkspaceMember({
      action: "disable",
      csrfToken,
      member,
      workspaceId: members.workspaceId,
    });
    setPendingMemberId(null);
    setConfirmation(null);
    await receiveMutation(result);
  }

  async function confirmTransfer() {
    if (!confirmation || pendingMemberId) return;
    const member = confirmation.member;
    setPendingMemberId(member.id);
    setNotice(null);
    const result = await transferWorkspaceOwnership({
      csrfToken,
      expectedWorkspaceUpdatedAt: workspaceUpdatedAt,
      member,
      workspaceId: members.workspaceId,
    });
    setPendingMemberId(null);
    setConfirmation(null);
    if (result.status === "success") {
      boundaryNavigate(
        result.href,
        `Владение пространством передано: ${member.name || member.email}.`,
      );
      return;
    }
    await receiveBoundaryFailure(result);
  }

  async function confirmLeave() {
    if (!confirmation || pendingMemberId) return;
    const member = confirmation.member;
    setPendingMemberId(member.id);
    setNotice(null);
    const result = await leaveWorkspace({
      csrfToken,
      currentWorkspaceId,
      member,
      workspaceId: members.workspaceId,
    });
    setPendingMemberId(null);
    setConfirmation(null);
    if (result.status === "success") {
      boundaryNavigate(result.href, "Вы вышли из рабочего пространства.");
      return;
    }
    await receiveBoundaryFailure(result);
  }

  async function reactivate(member: WorkspaceMemberDto) {
    if (pendingMemberId) return;
    setPendingMemberId(member.id);
    setNotice(null);
    const result = await transitionWorkspaceMember({
      action: "reactivate",
      csrfToken,
      member,
      workspaceId: members.workspaceId,
    });
    setPendingMemberId(null);
    await receiveMutation(result);
  }

  async function receiveMutation(
    result: Awaited<ReturnType<typeof updateWorkspaceMemberRole>>,
  ) {
    if (result.status === "success") {
      setMembers(result.members);
      onCommittedMutation?.();
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "conflict") {
      const fresh = await loadWorkspaceMembers(members.workspaceId);
      if (fresh.status === "success") setMembers(fresh.members);
      setNotice({
        message:
          "Список обновлён: данные участника изменились в другой вкладке.",
        tone: "warning",
      });
      return;
    }
    setNotice({ message: result.message, tone: "danger" });
  }

  async function receiveBoundaryFailure(
    result: Awaited<ReturnType<typeof transferWorkspaceOwnership>>,
  ) {
    if (result.status === "success") return;
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "conflict") {
      const fresh = await loadWorkspaceMembers(members.workspaceId);
      if (fresh.status === "success") setMembers(fresh.members);
      setNotice({
        message: `${result.message} Список участников обновлён.`,
        tone: "warning",
      });
      return;
    }
    setNotice({ message: result.message, tone: "danger" });
  }

  return (
    <section
      aria-labelledby="workspace-members-title"
      className={styles.section}
    >
      <div className={styles.sectionHeading}>
        <div>
          <h2 id="workspace-members-title">Участники</h2>
          <p>
            Роли определяют доступ к финансовым данным и действиям пространства.
          </p>
        </div>
        <span className={styles.memberCount}>{members.items.length}</span>
      </div>

      {notice ? (
        <InlineNotice
          role="status"
          title="Доступ не изменён"
          tone={notice.tone}
        >
          {notice.message}
        </InlineNotice>
      ) : null}

      {members.items.some((member) =>
        member.blockingReasonCodes.includes("workspace_fallback_required"),
      ) ? (
        <InlineNotice
          action={
            <Button
              onClick={() => boundaryNavigate("/app/workspaces")}
              tone="secondary"
            >
              Рабочие пространства
            </Button>
          }
          title="Для выхода нужно другое пространство"
          tone="neutral"
        >
          Сначала создайте другое пространство. Это сохранит явный финансовый
          контекст после выхода.
        </InlineNotice>
      ) : null}

      <div
        aria-label="Участники рабочего пространства"
        className={styles.memberList}
        role="list"
      >
        {members.items.map((member) => (
          <article className={styles.memberRow} key={member.id} role="listitem">
            <div aria-hidden="true" className={styles.memberAvatar}>
              {memberInitials(member)}
            </div>
            <div className={styles.memberIdentity}>
              <div className={styles.memberNameLine}>
                <strong>{member.name || member.email}</strong>
                {member.isSelf ? <span>Вы</span> : null}
              </div>
              {member.name ? <span>{member.email}</span> : null}
            </div>
            <div className={styles.memberRole}>
              {member.capabilities.canUpdateRole ? (
                <label>
                  <span className={styles.visuallyHidden}>
                    Роль: {member.name || member.email}
                  </span>
                  <select
                    aria-label={`Роль: ${member.name || member.email}`}
                    disabled={pendingMemberId !== null}
                    onChange={(event) =>
                      void changeRole(
                        member,
                        event.target.value as WorkspaceMemberDto["role"],
                      )
                    }
                    value={member.role}
                  >
                    {member.capabilities.assignableRoles.map((role) => (
                      <option key={role} value={role}>
                        {workspaceRoleOptionLabel(role)}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <span>{workspaceRoleLabel(member.role)}</span>
              )}
            </div>
            <StatusLabel
              tone={member.status === "active" ? "success" : "neutral"}
            >
              {member.status === "active" ? "Активен" : "Отключён"}
            </StatusLabel>
            <div className={styles.memberAction}>
              <div className={styles.memberActionGroup}>
                {member.capabilities.canTransferOwnership ? (
                  <Button
                    aria-label={`Передать владение участнику ${member.name || member.email}`}
                    disabled={pendingMemberId !== null}
                    onClick={() =>
                      setConfirmation({ kind: "transfer", member })
                    }
                    tone="secondary"
                  >
                    Передать
                  </Button>
                ) : null}
                {member.capabilities.canDisable ? (
                  <Button
                    disabled={pendingMemberId !== null}
                    onClick={() => setConfirmation({ kind: "disable", member })}
                    tone="dangerSecondary"
                  >
                    Отключить
                  </Button>
                ) : member.capabilities.canReactivate ? (
                  <Button
                    isLoading={pendingMemberId === member.id}
                    onClick={() => void reactivate(member)}
                    tone="secondary"
                  >
                    Восстановить
                  </Button>
                ) : member.capabilities.canLeave ? (
                  <Button
                    disabled={pendingMemberId !== null}
                    onClick={() => setConfirmation({ kind: "leave", member })}
                    tone="dangerSecondary"
                  >
                    Выйти
                  </Button>
                ) : member.capabilities.canTransferOwnership ? null : (
                  <span
                    aria-hidden="true"
                    className={styles.memberActionPlaceholder}
                  >
                    —
                  </span>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>

      {confirmation ? (
        <ConfirmationDialog
          confirmLabel={confirmationCopy(confirmation).confirmLabel}
          confirmTone={confirmation.kind === "transfer" ? "primary" : "danger"}
          description={confirmationCopy(confirmation).description}
          onCancel={() => setConfirmation(null)}
          onConfirm={() => {
            if (confirmation.kind === "disable") void confirmDisable();
            if (confirmation.kind === "transfer") void confirmTransfer();
            if (confirmation.kind === "leave") void confirmLeave();
          }}
          pending={pendingMemberId === confirmation.member.id}
          title={confirmationCopy(confirmation).title}
        />
      ) : null}
    </section>
  );
}

function confirmationCopy(confirmation: {
  kind: "disable" | "leave" | "transfer";
  member: WorkspaceMemberDto;
}) {
  const identity = confirmation.member.name || confirmation.member.email;
  if (confirmation.kind === "transfer") {
    return {
      title: "Передать владение?",
      description: `${identity} станет владельцем пространства. Ваша роль изменится на администратора, финансовые данные не изменятся.`,
      confirmLabel: "Передать владение",
    };
  }
  if (confirmation.kind === "leave") {
    return {
      title: "Выйти из пространства?",
      description:
        "Вы потеряете доступ к финансовым данным этого пространства. Активный контекст переключится на другое доступное пространство.",
      confirmLabel: "Выйти из пространства",
    };
  }
  return {
    title: "Отключить участника?",
    description: `Участник ${identity} потеряет доступ к данным этого пространства. Его активные сессии и Chat-состояние для пространства будут очищены.`,
    confirmLabel: "Отключить доступ",
  };
}

function memberInitials(member: WorkspaceMemberDto): string {
  const source = member.name?.trim() || member.email;
  const parts = source.split(/\s+/).filter(Boolean);
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
