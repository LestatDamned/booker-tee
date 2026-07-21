import { useRef, useState } from "react";

import { ActionStack } from "../../../ui/action-stack/action-stack";
import { Badge } from "../../../ui/badge/badge";
import { Button } from "../../../ui/button/button";
import { MoneyValue } from "../../../ui/money-value/money-value";
import { WorkbenchRow } from "../../../ui/workbench-row/workbench-row";
import type { ManualOperationDto } from "../api/manual-ledger-api";
import type { ManualOperationRowModel } from "./manual-ledger-model";
import { ManualOperationDelete } from "./manual-operation-delete";
import { ManualOperationEdit } from "./manual-operation-edit";
import { ManualOperationLifecycle } from "./manual-operation-lifecycle";
import styles from "../manual-ledger.module.css";

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
          <section
            aria-labelledby={`${editPanelId}-title`}
            className={styles.editExpansion}
          >
            <h3 id={`${editPanelId}-title`}>Исправить операцию</h3>
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
          </section>
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
      <Badge tone={operation.operationTone}>{operation.operationLabel}</Badge>
      {operation.transferRouteLabel ? (
        <Badge tone="transfer">{operation.transferRouteLabel}</Badge>
      ) : (
        <>
          {operation.categoryLabel ? (
            <Badge tone="category">{operation.categoryLabel}</Badge>
          ) : (
            <Badge tone="neutral">Без категории</Badge>
          )}
          {operation.propertyLabel ? (
            <span>Объект: {operation.propertyLabel}</span>
          ) : null}
          {operation.accountLabel ? (
            <span>Счёт: {operation.accountLabel}</span>
          ) : null}
        </>
      )}
      {problemStatus ? (
        <Badge tone={operation.statusTone}>{operation.statusLabel}</Badge>
      ) : (
        <span className={styles.flatStatus}>{operation.statusLabel}</span>
      )}
    </>
  );
}
