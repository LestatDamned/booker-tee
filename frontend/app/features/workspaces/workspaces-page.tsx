import { useEffect, useRef, useState, type FormEvent } from "react";

import { loadSession, type SessionDto } from "../../api/session";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { AppShell } from "../../shell/app-shell";
import { Button } from "../../ui/button/button";
import {
  InlineNotice,
  type InlineNoticeTone,
} from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchStatus } from "../../ui/workbench-content/workbench-status";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import {
  createWorkspace,
  selectWorkspace,
  type CreateWorkspaceDraft,
  type WorkspaceDirectoryDto,
  type WorkspaceDirectoryItemDto,
  type WorkspaceType,
} from "./api/workspaces-api";
import { WorkspaceCreatePanel } from "./workspace-create-panel";
import {
  firstInvalidWorkspaceField,
  validateWorkspaceDraft,
  workspaceFieldErrors,
  type WorkspaceFieldErrors,
} from "./workspace-form";
import { WorkspaceMobileList, WorkspaceTable } from "./workspace-records";
import styles from "./workspaces-page.module.css";

type BoundaryNavigate = (href: string, message?: string) => void;

type PageFailure = {
  message: string;
  title: string;
  tone: InlineNoticeTone;
};

export function WorkspacesPage({
  boundaryNavigate = defaultBoundaryNavigate,
  directory,
  session,
}: {
  boundaryNavigate?: BoundaryNavigate;
  directory: WorkspaceDirectoryDto;
  session: SessionDto;
}) {
  const nameRef = useRef<HTMLInputElement>(null);
  const createTriggerRef = useRef<HTMLButtonElement>(null);
  const mutationPendingRef = useRef(false);
  const [draft, setDraft] = useState(() => emptyDraft(directory));
  const [idempotencyKey, setIdempotencyKey] = useState(() =>
    crypto.randomUUID(),
  );
  const [fieldErrors, setFieldErrors] = useState<WorkspaceFieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [confirmCreateClose, setConfirmCreateClose] = useState(false);
  const [createPending, setCreatePending] = useState(false);
  const [switchPendingId, setSwitchPendingId] = useState<string | null>(null);
  const [failure, setFailure] = useState<PageFailure | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(() =>
    takeBoundaryNotice(),
  );
  const currentWorkspace = directory.items.find((item) => item.isCurrent);

  useEffect(() => {
    const heading = document.getElementById("workspaces-page-title");
    heading?.setAttribute("tabindex", "-1");
    heading?.focus();
    return () => heading?.removeAttribute("tabindex");
  }, []);

  function openCreate() {
    setDraft(emptyDraft(directory));
    setIdempotencyKey(crypto.randomUUID());
    setFieldErrors({});
    setSubmitError(null);
    setCreateOpen(true);
  }

  function changeDraft<FieldName extends keyof CreateWorkspaceDraft>(
    field: FieldName,
    value: CreateWorkspaceDraft[FieldName],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setIdempotencyKey(crypto.randomUUID());
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutationPendingRef.current) return;
    const errors = validateWorkspaceDraft(draft);
    setFieldErrors(errors);
    setSubmitError(null);
    const invalidField = firstInvalidWorkspaceField(errors);
    if (invalidField) {
      focusWorkspaceField(invalidField, nameRef.current);
      return;
    }
    mutationPendingRef.current = true;
    setCreatePending(true);
    const result = await createWorkspace({
      csrfToken: session.csrfToken,
      draft,
      idempotencyKey,
    });
    mutationPendingRef.current = false;
    setCreatePending(false);
    if (result.status === "success") {
      boundaryNavigate(
        result.href,
        `Пространство «${result.workspace.name}» создано и выбрано.`,
      );
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "error" && result.code === "network_error") {
      const committed = await sessionBoundaryChanged(
        directory.currentWorkspaceId,
      );
      if (committed) {
        boundaryNavigate("/app/workspaces");
        return;
      }
    }
    if (result.status === "conflict") {
      setSubmitError(result.message);
      return;
    }
    const serverErrors = workspaceFieldErrors(result.fieldErrors);
    setFieldErrors(serverErrors);
    setSubmitError(result.message);
    const serverInvalidField = firstInvalidWorkspaceField(serverErrors);
    if (serverInvalidField) {
      focusWorkspaceField(serverInvalidField, nameRef.current);
    }
  }

  async function switchWorkspace(workspace: WorkspaceDirectoryItemDto) {
    if (mutationPendingRef.current) return;
    mutationPendingRef.current = true;
    setFailure(null);
    setSuccessMessage(null);
    setSwitchPendingId(workspace.id);
    const result = await selectWorkspace({
      csrfToken: session.csrfToken,
      currentWorkspaceId: directory.currentWorkspaceId,
      workspaceId: workspace.id,
    });
    mutationPendingRef.current = false;
    setSwitchPendingId(null);
    if (result.status === "success") {
      boundaryNavigate(
        result.href,
        `Текущее пространство: «${workspace.name}».`,
      );
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "error" && result.code === "network_error") {
      const committed = await sessionBoundaryChanged(
        directory.currentWorkspaceId,
      );
      if (committed) {
        boundaryNavigate("/app/workspaces");
        return;
      }
    }
    if (result.status === "conflict") {
      setFailure({
        title: "Контекст изменился в другой вкладке",
        message: result.message,
        tone: "warning",
      });
      return;
    }
    if (result.status === "not_found") {
      setFailure({
        title: "Пространство больше недоступно",
        message: result.message,
        tone: "warning",
      });
      return;
    }
    setFailure({
      title: "Не удалось переключить пространство",
      message: result.message,
      tone: "danger",
    });
  }

  function requestCreateClose() {
    if (workspaceDraftIsDirty(draft, directory)) {
      setConfirmCreateClose(true);
      return;
    }
    closeCreate();
  }

  function closeCreate() {
    setDraft(emptyDraft(directory));
    setFieldErrors({});
    setSubmitError(null);
    setConfirmCreateClose(false);
    setCreateOpen(false);
  }

  const createAction = directory.capabilities.canCreate ? (
    <Button
      ref={createTriggerRef}
      aria-haspopup="dialog"
      icon="plus"
      onClick={openCreate}
      tone="primary"
    >
      Создать пространство
    </Button>
  ) : null;

  return (
    <AppShell session={session}>
      <PageFrame>
        <WorkbenchSurface className={styles.workbench}>
          <WorkbenchHeader>
            <PageHeader
              actions={directory.items.length === 0 ? null : createAction}
              description={
                currentWorkspace
                  ? `Сейчас: ${currentWorkspace.name}. Выберите контекст, в котором будут открываться финансовые данные.`
                  : "Создайте финансовый контекст, чтобы начать работу."
              }
              eyebrow="Финансовый контекст"
              title="Пространства"
              titleId="workspaces-page-title"
            />
          </WorkbenchHeader>

          <WorkbenchStatus className={styles.directoryStatus}>
            <span>{workspaceCountLabel(directory.items.length)}</span>
            {currentWorkspace ? (
              <span>
                Текущее: <strong>{currentWorkspace.name}</strong>
              </span>
            ) : null}
          </WorkbenchStatus>

          {successMessage ? (
            <InlineNotice
              action={
                <Button onClick={() => setSuccessMessage(null)} tone="ghost">
                  Закрыть
                </Button>
              }
              className={styles.notice}
              role="status"
              title="Готово"
              tone="success"
            >
              {successMessage}
            </InlineNotice>
          ) : null}

          {failure ? (
            <InlineNotice
              action={
                <Button
                  icon="retry"
                  onClick={() => boundaryNavigate("/app/workspaces")}
                  tone="secondary"
                >
                  Обновить
                </Button>
              }
              className={styles.notice}
              role="alert"
              title={failure.title}
              tone={failure.tone}
            >
              {failure.message}
            </InlineNotice>
          ) : null}

          {directory.items.length === 0 ? (
            <WorkbenchEmptyState
              action={createAction}
              icon="properties"
              title="Нет доступных пространств"
            >
              Создайте пространство явно — приложение не создаёт финансовый
              контекст скрыто при чтении страницы.
            </WorkbenchEmptyState>
          ) : (
            <ResponsiveRecordCollection
              mobileList={
                <WorkspaceMobileList
                  items={directory.items}
                  onSelect={(workspace) => void switchWorkspace(workspace)}
                  pendingId={switchPendingId}
                />
              }
              table={
                <WorkspaceTable
                  items={directory.items}
                  onSelect={(workspace) => void switchWorkspace(workspace)}
                  pendingId={switchPendingId}
                />
              }
            />
          )}
        </WorkbenchSurface>
      </PageFrame>

      {createOpen ? (
        <WorkspaceCreatePanel
          confirmClose={confirmCreateClose}
          directory={directory}
          draft={draft}
          fieldErrors={fieldErrors}
          nameRef={nameRef}
          onCancelConfirm={() => setConfirmCreateClose(false)}
          onChange={changeDraft}
          onClose={requestCreateClose}
          onConfirmClose={closeCreate}
          onSubmit={(event) => void submitCreate(event)}
          pending={createPending}
          submitError={submitError}
        />
      ) : null}
    </AppShell>
  );
}

async function sessionBoundaryChanged(expectedWorkspaceId: string) {
  const result = await loadSession();
  return (
    result.status === "authenticated" &&
    result.session.workspace.id !== expectedWorkspaceId
  );
}

function emptyDraft(directory: WorkspaceDirectoryDto): CreateWorkspaceDraft {
  return {
    name: "",
    workspaceType: (directory.workspaceTypeOptions[0]?.value ??
      "personal") as WorkspaceType,
    defaultCurrency: directory.currencyOptions[0]?.value ?? "RUB",
  };
}

function workspaceDraftIsDirty(
  draft: CreateWorkspaceDraft,
  directory: WorkspaceDirectoryDto,
): boolean {
  const empty = emptyDraft(directory);
  return (
    draft.name.trim().length > 0 ||
    draft.workspaceType !== empty.workspaceType ||
    draft.defaultCurrency !== empty.defaultCurrency
  );
}

function focusWorkspaceField(
  field: keyof CreateWorkspaceDraft,
  nameInput: HTMLInputElement | null,
) {
  if (field === "name") {
    nameInput?.focus();
    return;
  }
  const id =
    field === "workspaceType" ? "workspace-type" : "workspace-currency";
  document.getElementById(id)?.focus();
}

function workspaceCountLabel(count: number): string {
  if (count % 10 === 1 && count % 100 !== 11) return `${count} пространство`;
  if ([2, 3, 4].includes(count % 10) && ![12, 13, 14].includes(count % 100)) {
    return `${count} пространства`;
  }
  return `${count} пространств`;
}

const BOUNDARY_NOTICE_KEY = "booker-tee:workspace-boundary-notice";

function defaultBoundaryNavigate(href: string, message?: string) {
  if (message) {
    try {
      window.sessionStorage.setItem(BOUNDARY_NOTICE_KEY, message);
    } catch {
      // Boundary navigation remains safe when browser storage is unavailable.
    }
  }
  window.location.replace(href);
}

function takeBoundaryNotice(): string | null {
  try {
    const message = window.sessionStorage.getItem(BOUNDARY_NOTICE_KEY);
    window.sessionStorage.removeItem(BOUNDARY_NOTICE_KEY);
    return message;
  } catch {
    return null;
  }
}
