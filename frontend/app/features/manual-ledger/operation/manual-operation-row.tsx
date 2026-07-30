import { useRef, useState } from "react";

import { ActionStack } from "../../../ui/action-stack/action-stack";
import { Button } from "../../../ui/button/button";
import { MoneyValue } from "../../../ui/money-value/money-value";
import { StatusLabel } from "../../../ui/status-label/status-label";
import { Tag } from "../../../ui/tag/tag";
import {
  WorkbenchRow,
  WorkbenchRowExpansion,
} from "../../../ui/workbench-row/workbench-row";
import type { ManualOperationDto } from "../api/manual-ledger-api";
import type { ManualOperationRowModel } from "./manual-ledger-model";
import { ManualOperationDelete } from "./manual-operation-delete";
import { ManualOperationEdit } from "./manual-operation-edit";
import { ManualOperationLifecycle } from "./manual-operation-lifecycle";

type ManualOperationRowProps = {
  csrfToken: string;
  isEditing: boolean;
  isTargeted: boolean;
  isWorking: boolean;
  onDeleted?: (operationId: string) => void;
  onEdit: (operationId: string) => void;
  onEditClosed: () => void;
  onRefresh?: () => void;
  onOperationUpdated?: (operation: ManualOperationDto) => void;
  onWorkStarted: () => void;
  operation: ManualOperationRowModel;
};

export function ManualOperationRow({
  csrfToken,
  isEditing,
  isTargeted,
  isWorking,
  onDeleted,
  onEdit,
  onEditClosed,
  onRefresh,
  onOperationUpdated,
  onWorkStarted,
  operation,
}: ManualOperationRowProps) {
  const [mutationPending, setMutationPending] = useState(false);
  const editButtonRef = useRef<HTMLButtonElement>(null);
  const editPanelId = `manual-operation-edit-panel-${operation.id}`;

  function closeEdit() {
    onEditClosed();
    queueMicrotask(() => editButtonRef.current?.focus());
  }

  return (
    <WorkbenchRow
      aside={
        operation.canEdit ||
        operation.canCancel ||
        operation.canRestore ||
        operation.canDelete ? (
          <ActionStack
            danger={
              !isEditing && (operation.canCancel || operation.canDelete) ? (
                <>
                  {operation.canCancel ? (
                    <ManualOperationLifecycle
                      action="cancel"
                      csrfToken={csrfToken}
                      disabled={mutationPending}
                      onPendingChange={setMutationPending}
                      {...(onRefresh === undefined ? {} : { onRefresh })}
                      {...(onOperationUpdated === undefined
                        ? {}
                        : { onUpdated: onOperationUpdated })}
                      operationId={operation.id}
                      version={operation.version}
                    />
                  ) : null}
                  {operation.canDelete ? (
                    <ManualOperationDelete
                      csrfToken={csrfToken}
                      disabled={mutationPending}
                      {...(onDeleted === undefined ? {} : { onDeleted })}
                      onPendingChange={setMutationPending}
                      {...(onRefresh === undefined ? {} : { onRefresh })}
                      operationId={operation.id}
                      version={operation.version}
                    />
                  ) : null}
                </>
              ) : undefined
            }
            primary={
              operation.canEdit ? (
                <Button
                  aria-controls={editPanelId}
                  aria-expanded={isEditing}
                  disabled={mutationPending}
                  onClick={() =>
                    isEditing ? closeEdit() : onEdit(operation.id)
                  }
                  ref={editButtonRef}
                  tone="secondary"
                  icon="edit"
                >
                  {isEditing ? "Закрыть" : "Исправить"}
                </Button>
              ) : operation.canRestore ? (
                <ManualOperationLifecycle
                  action="restore"
                  csrfToken={csrfToken}
                  disabled={mutationPending}
                  onPendingChange={setMutationPending}
                  {...(onRefresh === undefined ? {} : { onRefresh })}
                  {...(onOperationUpdated === undefined
                    ? {}
                    : { onUpdated: onOperationUpdated })}
                  operationId={operation.id}
                  version={operation.version}
                />
              ) : undefined
            }
          />
        ) : undefined
      }
      date={operation.date}
      description={operation.description}
      id={operation.anchorId}
      expansion={
        operation.canEdit && isEditing ? (
          <WorkbenchRowExpansion
            title="Исправить операцию"
            titleId={`${editPanelId}-title`}
          >
            <ManualOperationEdit
              csrfToken={csrfToken}
              disabled={mutationPending}
              onClose={closeEdit}
              onPendingChange={setMutationPending}
              {...(onOperationUpdated === undefined
                ? {}
                : { onUpdated: onOperationUpdated })}
              operationId={operation.id}
            />
          </WorkbenchRowExpansion>
        ) : undefined
      }
      meta={<OperationMeta operation={operation} />}
      onAction={onWorkStarted}
      state={isWorking ? "working" : isTargeted ? "target" : "default"}
      value={
        operation.money ? (
          <MoneyValue
            amount={operation.money.amount}
            currency={operation.money.currency}
            tone={operation.money.tone}
          />
        ) : undefined
      }
    />
  );
}

function OperationMeta({ operation }: { operation: ManualOperationRowModel }) {
  const problemStatus =
    operation.statusTone === "warning" || operation.statusTone === "danger";
  return (
    <>
      <Tag tone={operation.operationTone}>{operation.operationLabel}</Tag>
      {operation.transferRouteLabel ? (
        <Tag tone="transfer">{operation.transferRouteLabel}</Tag>
      ) : (
        <>
          {operation.categoryLabel ? (
            <Tag tone="category">{operation.categoryLabel}</Tag>
          ) : (
            <Tag tone="neutral">Без категории</Tag>
          )}
          {operation.propertyLabel ? (
            <span>Объект: {operation.propertyLabel}</span>
          ) : null}
          {operation.accountLabel ? (
            <span>Счёт: {operation.accountLabel}</span>
          ) : null}
        </>
      )}
      <StatusLabel
        tone={operation.statusTone}
        variant={problemStatus ? "soft" : "plain"}
      >
        {operation.statusLabel}
      </StatusLabel>
    </>
  );
}
