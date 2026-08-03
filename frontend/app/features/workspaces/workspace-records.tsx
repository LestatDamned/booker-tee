import { Button } from "../../ui/button/button";
import { StatusLabel } from "../../ui/status-label/status-label";
import { Tag } from "../../ui/tag/tag";
import type { WorkspaceDirectoryItemDto } from "./api/workspaces-api";
import { workspaceRoleLabel, workspaceTypeLabel } from "./workspace-labels";
import styles from "./workspaces-page.module.css";

type WorkspaceRecordsProps = {
  items: WorkspaceDirectoryItemDto[];
  onSelect: (workspace: WorkspaceDirectoryItemDto) => void;
  pendingId: string | null;
};

export function WorkspaceTable({
  items,
  onSelect,
  pendingId,
}: WorkspaceRecordsProps) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">Доступные пространства</caption>
      <thead>
        <tr>
          <th scope="col">Пространство</th>
          <th scope="col">Тип и валюта</th>
          <th scope="col">Ваш доступ</th>
          <th scope="col">Состояние</th>
          <th scope="col">
            <span className="visually-hidden">Действие</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {items.map((workspace) => (
          <tr
            aria-current={workspace.isCurrent ? "true" : undefined}
            className={recordClassName(workspace)}
            data-workspace-record
            key={workspace.id}
          >
            <th scope="row">
              <strong data-record-identity>{workspace.name}</strong>
              <span className={styles.recordHint}>Финансовый контекст</span>
            </th>
            <td>
              <WorkspaceTypeAndCurrency workspace={workspace} />
            </td>
            <td>{workspaceRoleLabel(workspace.membership.role)}</td>
            <td>
              <WorkspaceStatus workspace={workspace} />
            </td>
            <td className={styles.actionCell}>
              <WorkspaceSelectAction
                allPending={pendingId !== null}
                onSelect={onSelect}
                pending={pendingId === workspace.id}
                workspace={workspace}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function WorkspaceMobileList({
  items,
  onSelect,
  pendingId,
}: WorkspaceRecordsProps) {
  return (
    <ol aria-label="Доступные пространства">
      {items.map((workspace) => (
        <li key={workspace.id}>
          <article
            aria-current={workspace.isCurrent ? "true" : undefined}
            className={recordClassName(workspace)}
            data-responsive-record
            data-workspace-record
          >
            <div className={styles.mobileHeading}>
              <div>
                <h2 data-record-identity>{workspace.name}</h2>
                <p>
                  {workspaceTypeLabel(workspace.type)} ·{" "}
                  {workspace.defaultCurrency}
                </p>
              </div>
              <WorkspaceStatus workspace={workspace} />
            </div>
            <dl className={styles.mobileFacts}>
              <div>
                <dt>Ваш доступ</dt>
                <dd>{workspaceRoleLabel(workspace.membership.role)}</dd>
              </div>
              <div>
                <dt>Тип</dt>
                <dd>{workspaceTypeLabel(workspace.type)}</dd>
              </div>
              <div>
                <dt>Валюта</dt>
                <dd>{workspace.defaultCurrency}</dd>
              </div>
            </dl>
            {workspace.capabilities.canSelect ? (
              <div className={styles.mobileAction}>
                <WorkspaceSelectAction
                  allPending={pendingId !== null}
                  onSelect={onSelect}
                  pending={pendingId === workspace.id}
                  workspace={workspace}
                />
              </div>
            ) : null}
          </article>
        </li>
      ))}
    </ol>
  );
}

function WorkspaceTypeAndCurrency({
  workspace,
}: {
  workspace: WorkspaceDirectoryItemDto;
}) {
  return (
    <span className={styles.typeCurrency}>
      <Tag>{workspaceTypeLabel(workspace.type)}</Tag>
      <span>{workspace.defaultCurrency}</span>
    </span>
  );
}

function WorkspaceStatus({
  workspace,
}: {
  workspace: WorkspaceDirectoryItemDto;
}) {
  if (workspace.isCurrent) {
    return (
      <StatusLabel tone="information" variant="soft">
        Текущее
      </StatusLabel>
    );
  }
  if (!workspace.isActive) {
    return <StatusLabel tone="neutral">Неактивно</StatusLabel>;
  }
  return <StatusLabel tone="success">Доступно</StatusLabel>;
}

function WorkspaceSelectAction({
  allPending,
  onSelect,
  pending,
  workspace,
}: {
  allPending: boolean;
  onSelect: WorkspaceRecordsProps["onSelect"];
  pending: boolean;
  workspace: WorkspaceDirectoryItemDto;
}) {
  if (!workspace.capabilities.canSelect) return null;
  return (
    <Button
      aria-label={`Перейти в пространство «${workspace.name}»`}
      className={styles.switchAction ?? ""}
      disabled={allPending}
      isLoading={pending}
      onClick={() => onSelect(workspace)}
      tone="primary"
    >
      {pending ? "Переключаем…" : "Перейти"}
    </Button>
  );
}

function recordClassName(workspace: WorkspaceDirectoryItemDto): string {
  return [
    styles.record,
    workspace.isCurrent ? styles.currentRecord : "",
    !workspace.isActive ? styles.inactiveRecord : "",
  ]
    .filter(Boolean)
    .join(" ");
}
