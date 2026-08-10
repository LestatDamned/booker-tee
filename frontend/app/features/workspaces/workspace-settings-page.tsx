import { useRef, useState, type FormEvent } from "react";

import type { SessionDto } from "../../api/session";
import type { WorkspaceActivityLoadResult } from "./api/workspace-activity-api";
import type { WorkspaceMembersDto } from "./api/workspace-members-api";
import type { WorkspaceInvitationsDto } from "./api/workspace-invitations-api";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { AppShell } from "../../shell/app-shell";
import { BackLink } from "../../ui/back-link/back-link";
import { Button } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { StatusLabel } from "../../ui/status-label/status-label";
import { Tag } from "../../ui/tag/tag";
import { ToastViewport, useToastQueue } from "../../ui/toast/toast";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import {
  loadWorkspaceSettings,
  updateWorkspaceSettings,
  type WorkspaceSettingsDraft,
  type WorkspaceSettingsDto,
} from "./api/workspace-settings-api";
import {
  firstInvalidWorkspaceField,
  validateWorkspaceDraft,
  workspaceFieldErrors,
  type WorkspaceFieldErrors,
} from "./workspace-form";
import { WorkspaceLifecycleImpact } from "./workspace-lifecycle-impact";
import { WorkspaceActivitySection } from "./workspace-activity-section";
import { WorkspaceInvitationsSection } from "./workspace-invitations-section";
import { WorkspaceMembersSection } from "./workspace-members-section";
import { workspaceRoleLabel, workspaceTypeLabel } from "./workspace-labels";
import {
  WorkspaceReadOnlySettings,
  WorkspaceSettingsForm,
} from "./workspace-settings-fields";
import styles from "./workspace-settings-page.module.css";

export function WorkspaceSettingsPage({
  boundaryNavigate = defaultBoundaryNavigate,
  initialActivity,
  initialSettings,
  initialMembers,
  initialInvitations,
  navigationPending = false,
  session,
}: {
  boundaryNavigate?: (href: string, message?: string) => void;
  initialActivity: WorkspaceActivityLoadResult | null;
  initialSettings: WorkspaceSettingsDto;
  initialMembers: WorkspaceMembersDto | null;
  initialInvitations: WorkspaceInvitationsDto | null;
  navigationPending?: boolean;
  session: SessionDto;
}) {
  const nameRef = useRef<HTMLInputElement>(null);
  const pendingRef = useRef(false);
  const [settings, setSettings] = useState(initialSettings);
  const [draft, setDraft] = useState(() => settingsDraft(initialSettings));
  const [fieldErrors, setFieldErrors] = useState<WorkspaceFieldErrors>({});
  const [failure, setFailure] = useState<{
    canReload: boolean;
    message: string;
    title: string;
    tone: "danger" | "warning";
  } | null>(null);
  const [pending, setPending] = useState(false);
  const [activityRefreshToken, setActivityRefreshToken] = useState(0);
  const [boundaryNotice] = useState(() => takeBoundaryNotice());
  const { dismissToast, showToast, toast } = useToastQueue();
  const workspace = settings.workspace;
  const dirty = workspaceSettingsDraftIsDirty(draft, settings);
  const shellSession =
    workspace.id === session.workspace.id
      ? {
          ...session,
          workspace: {
            ...session.workspace,
            defaultCurrency: workspace.defaultCurrency,
            name: workspace.name,
            type: workspace.type,
          },
        }
      : session;

  function changeDraft<FieldName extends keyof WorkspaceSettingsDraft>(
    field: FieldName,
    value: WorkspaceSettingsDraft[FieldName],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setFailure(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current || !workspace.capabilities.canUpdate) return;
    const errors = validateWorkspaceDraft(draft);
    setFieldErrors(errors);
    const invalid = firstInvalidWorkspaceField(errors);
    if (invalid) {
      focusWorkspaceSettingsField(invalid, nameRef.current);
      return;
    }
    pendingRef.current = true;
    setPending(true);
    setFailure(null);
    const result = await updateWorkspaceSettings({
      csrfToken: session.csrfToken,
      draft,
      expectedUpdatedAt: workspace.updatedAt,
      workspaceId: workspace.id,
    });
    pendingRef.current = false;
    setPending(false);
    if (result.status === "success") {
      setSettings(result.settings);
      setDraft(settingsDraft(result.settings));
      setFieldErrors({});
      showToast({ message: "Настройки пространства сохранены." });
      setActivityRefreshToken((current) => current + 1);
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "conflict") {
      await reloadAfterConflict();
      return;
    }
    if (result.status === "not_found" || result.status === "forbidden") {
      setFailure({
        canReload: false,
        message: result.message,
        title: "Не удалось сохранить настройки",
        tone: "danger",
      });
      return;
    }
    const serverErrors = workspaceFieldErrors(result.fieldErrors);
    setFieldErrors(serverErrors);
    setFailure({
      canReload: false,
      message: result.message,
      title: "Не удалось сохранить настройки",
      tone: "danger",
    });
    const invalidServerField = firstInvalidWorkspaceField(serverErrors);
    if (invalidServerField) {
      focusWorkspaceSettingsField(invalidServerField, nameRef.current);
    }
  }

  async function reloadAfterConflict() {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    const result = await loadWorkspaceSettings(workspace.id);
    pendingRef.current = false;
    setPending(false);
    if (result.status === "success") {
      setSettings(result.settings);
      setDraft(settingsDraft(result.settings));
      setFieldErrors({});
      setFailure({
        canReload: false,
        message:
          "Мы загрузили актуальные значения. Повторите нужное изменение и сохраните ещё раз.",
        title: "Настройки изменились в другой вкладке",
        tone: "warning",
      });
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setFailure({
      canReload: true,
      message:
        result.status === "not_found"
          ? "Пространство больше недоступно."
          : result.message,
      title: "Не удалось загрузить актуальные настройки",
      tone: "danger",
    });
  }

  return (
    <AppShell session={shellSession}>
      <PageFrame mobileTop="compact" spacing="block">
        <WorkbenchSurface
          aria-busy={navigationPending || pending}
          className={styles.workbench}
        >
          <WorkbenchHeader>
            <BackLink className={styles.backLink} to="/workspaces">
              Рабочие пространства
            </BackLink>
            <PageHeader
              description="Основные параметры и связанные данные пространства."
              eyebrow="Рабочее пространство"
              title={workspace.name}
            />
            <div className={styles.identityMeta}>
              <Tag>{workspaceTypeLabel(workspace.type)}</Tag>
              <Tag>{workspace.defaultCurrency}</Tag>
              <StatusLabel tone={workspace.isActive ? "success" : "neutral"}>
                {workspace.isActive ? "Активно" : "Неактивно"}
              </StatusLabel>
              <span>{workspaceRoleLabel(workspace.membership.role)}</span>
            </div>
          </WorkbenchHeader>

          {failure ? (
            <InlineNotice
              action={
                failure.canReload ? (
                  <Button
                    disabled={pending}
                    icon="retry"
                    isLoading={pending}
                    onClick={() => void reloadAfterConflict()}
                    tone="secondary"
                  >
                    Повторить загрузку
                  </Button>
                ) : undefined
              }
              className={styles.notice}
              role="alert"
              title={failure.title}
              tone={failure.tone}
            >
              {failure.message}
            </InlineNotice>
          ) : null}

          {boundaryNotice ? (
            <InlineNotice
              className={styles.notice}
              role="status"
              title="Владение передано"
              tone="success"
            >
              {boundaryNotice}
            </InlineNotice>
          ) : null}

          <WorkbenchContent
            aria-label="Общие настройки пространства"
            className={styles.content}
            isEmpty={false}
          >
            <section
              aria-labelledby="workspace-identity-title"
              className={styles.section}
            >
              <div className={styles.sectionHeading}>
                <div>
                  <h2 id="workspace-identity-title">Основные данные</h2>
                  <p>Название и параметры для новых счетов и операций.</p>
                </div>
                {!workspace.capabilities.canUpdate ? (
                  <StatusLabel tone="neutral">Только чтение</StatusLabel>
                ) : null}
              </div>

              {workspace.capabilities.canUpdate ? (
                <WorkspaceSettingsForm
                  currencyOptions={settings.currencyOptions}
                  draft={draft}
                  fieldErrors={fieldErrors}
                  nameRef={nameRef}
                  onChange={changeDraft}
                  onReset={() => {
                    setDraft(settingsDraft(settings));
                    setFieldErrors({});
                    setFailure(null);
                  }}
                  onSubmit={(event) => void submit(event)}
                  pending={pending}
                  typeOptions={settings.workspaceTypeOptions}
                  dirty={dirty}
                />
              ) : (
                <WorkspaceReadOnlySettings settings={settings} />
              )}
            </section>

            {initialMembers && initialInvitations ? (
              <>
                <WorkspaceMembersSection
                  boundaryNavigate={boundaryNavigate}
                  csrfToken={session.csrfToken}
                  currentWorkspaceId={session.workspace.id}
                  initialMembers={initialMembers}
                  onCommittedMutation={() =>
                    setActivityRefreshToken((current) => current + 1)
                  }
                  workspaceUpdatedAt={workspace.updatedAt}
                />

                <WorkspaceInvitationsSection
                  csrfToken={session.csrfToken}
                  initialInvitations={initialInvitations}
                  onCommittedMutation={() =>
                    setActivityRefreshToken((current) => current + 1)
                  }
                />
              </>
            ) : null}

            {initialActivity ? (
              <WorkspaceActivitySection
                initialResult={initialActivity}
                refreshToken={activityRefreshToken}
                workspaceId={workspace.id}
              />
            ) : null}

            <WorkspaceLifecycleImpact
              boundaryNavigate={boundaryNavigate}
              csrfToken={session.csrfToken}
              currentWorkspaceId={session.workspace.id}
              onConflict={reloadAfterConflict}
              settings={settings}
            />
          </WorkbenchContent>
        </WorkbenchSurface>
      </PageFrame>
      <ToastViewport onDismiss={dismissToast} toast={toast} />
    </AppShell>
  );
}

const BOUNDARY_NOTICE_KEY = "booker-tee:workspace-boundary-notice";

function defaultBoundaryNavigate(href: string, message?: string) {
  if (message) sessionStorage.setItem(BOUNDARY_NOTICE_KEY, message);
  window.location.assign(href);
}

function takeBoundaryNotice(): string | null {
  const message = sessionStorage.getItem(BOUNDARY_NOTICE_KEY);
  sessionStorage.removeItem(BOUNDARY_NOTICE_KEY);
  return message;
}

function settingsDraft(settings: WorkspaceSettingsDto): WorkspaceSettingsDraft {
  return {
    name: settings.workspace.name,
    workspaceType: settings.workspace.type,
    defaultCurrency: settings.workspace.defaultCurrency,
  };
}

function workspaceSettingsDraftIsDirty(
  draft: WorkspaceSettingsDraft,
  settings: WorkspaceSettingsDto,
) {
  const original = settingsDraft(settings);
  return (
    draft.name !== original.name ||
    draft.workspaceType !== original.workspaceType ||
    draft.defaultCurrency !== original.defaultCurrency
  );
}

function focusWorkspaceSettingsField(
  field: keyof WorkspaceSettingsDraft,
  nameInput: HTMLInputElement | null,
) {
  if (field === "name") {
    nameInput?.focus();
    return;
  }
  document.getElementById(`workspace-settings-${field}`)?.focus();
}
