import { useRef, useState } from "react";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import {
  transitionWorkspaceLifecycle,
  type WorkspaceSettingsDto,
} from "./api/workspace-settings-api";
import { Fact } from "./workspace-settings-fields";
import styles from "./workspace-settings-page.module.css";

type LifecycleAction = "deactivate" | "restore";

export function WorkspaceLifecycleImpact({
  boundaryNavigate,
  csrfToken,
  currentWorkspaceId,
  onConflict,
  settings,
}: {
  boundaryNavigate: (href: string, message?: string) => void;
  csrfToken: string;
  currentWorkspaceId: string;
  onConflict: () => Promise<void>;
  settings: WorkspaceSettingsDto;
}) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [confirmation, setConfirmation] = useState<LifecycleAction | null>(
    null,
  );
  const [failure, setFailure] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const workspace = settings.workspace;
  const impact = settings.lifecycleImpact;

  async function confirm() {
    if (!confirmation || pending) return;
    setPending(true);
    setFailure(null);
    const result = await transitionWorkspaceLifecycle({
      action: confirmation,
      csrfToken,
      expectedCurrentWorkspaceId: currentWorkspaceId,
      expectedWorkspaceUpdatedAt: workspace.updatedAt,
      workspaceId: workspace.id,
    });
    setPending(false);
    if (result.status === "success") {
      boundaryNavigate(
        result.href,
        confirmation === "deactivate"
          ? "Рабочее пространство деактивировано."
          : "Рабочее пространство восстановлено.",
      );
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setConfirmation(null);
    if (result.status === "conflict") {
      await onConflict();
      return;
    }
    setFailure(result.message);
  }

  const fallbackRequired = workspace.blockingReasonCodes.includes(
    "workspace_fallback_required",
  );
  const canTransition =
    workspace.capabilities.canDeactivate || workspace.capabilities.canRestore;

  return (
    <section
      aria-labelledby="workspace-lifecycle-title"
      className={styles.section}
    >
      <div className={styles.sectionHeading}>
        <div>
          <h2 id="workspace-lifecycle-title">Состояние пространства</h2>
          <p>Финансовая история сохраняется при деактивации.</p>
        </div>
        {canTransition ? (
          <Button
            onClick={() => {
              setFailure(null);
              setConfirmation(
                workspace.capabilities.canRestore ? "restore" : "deactivate",
              );
            }}
            ref={triggerRef}
            tone={
              workspace.capabilities.canRestore
                ? "secondary"
                : "dangerSecondary"
            }
          >
            {workspace.capabilities.canRestore
              ? "Восстановить"
              : "Деактивировать"}
          </Button>
        ) : null}
      </div>

      {failure ? (
        <InlineNotice
          role="alert"
          title="Не удалось изменить состояние"
          tone="danger"
        >
          {failure}
        </InlineNotice>
      ) : null}

      {fallbackRequired ? (
        <InlineNotice title="Нужно другое активное пространство" tone="warning">
          Сначала создайте или выберите пространство, куда можно безопасно
          перенести активные сессии.
        </InlineNotice>
      ) : impact ? (
        <InlineNotice title="Финансовая история сохранится" tone="information">
          Счета, импорты, правила, операции и отчёты не будут удалены.
        </InlineNotice>
      ) : (
        <InlineNotice title="Доступно только владельцу" tone="neutral">
          Сведения о сессиях, приглашениях и подключениях скрыты.
        </InlineNotice>
      )}

      {impact ? (
        <dl className={styles.impactGrid}>
          <Fact
            label="Активные сессии"
            value={String(impact.currentSessionCount)}
          />
          <Fact
            label="Приглашения"
            value={String(impact.pendingInvitationCount)}
          />
          <Fact
            label="Интеграции"
            value={String(impact.activeIntegrationConnectionCount)}
          />
          <Fact
            label="Подключения к чату"
            value={String(impact.activeChatIdentityBindingCount)}
          />
        </dl>
      ) : null}

      {confirmation ? (
        <ConfirmationDialog
          confirmLabel={
            confirmation === "deactivate"
              ? "Да, деактивировать"
              : "Восстановить пространство"
          }
          confirmTone={confirmation === "deactivate" ? "danger" : "primary"}
          description={
            confirmation === "deactivate"
              ? "Сессии перейдут в другие доступные пространства. Приглашения будут отозваны, а интеграции и Chat — отключены. Финансовые данные останутся на месте."
              : "Пространство снова станет доступно. Приглашения, интеграции и Chat останутся отключёнными, пока вы не настроите их заново."
          }
          onCancel={() => setConfirmation(null)}
          onConfirm={() => void confirm()}
          pending={pending}
          returnFocusRef={triggerRef}
          title={
            confirmation === "deactivate"
              ? "Деактивировать пространство?"
              : "Восстановить пространство?"
          }
        />
      ) : null}
    </section>
  );
}
