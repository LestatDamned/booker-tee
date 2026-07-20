import { useRef, useState } from "react";

import { Badge } from "../../ui/badge/badge";
import { Button } from "../../ui/button/button";
import { MoneyValue } from "../../ui/money-value/money-value";
import { WorkbenchRow } from "../../ui/workbench-row/workbench-row";
import type { ManualOperationDto } from "./manual-ledger-api";
import styles from "./manual-ledger.module.css";
import type { ManualOperationRowModel } from "./manual-ledger-model";
import { ManualOperationDelete } from "./manual-operation-delete";
import { ManualOperationEdit } from "./manual-operation-edit";
import { ManualOperationLifecycle } from "./manual-operation-lifecycle";

type ManualOperationRowProps = {
  csrfToken: string;
  isTargeted: boolean;
  onDeleted?: (operationId: string) => void;
  onRefresh?: () => void;
  onOperationUpdated?: (operation: ManualOperationDto) => void;
  operation: ManualOperationRowModel;
};

export function ManualOperationRow({
  csrfToken,
  isTargeted,
  onDeleted,
  onRefresh,
  onOperationUpdated,
  operation,
}: ManualOperationRowProps) {
  const [editOpen, setEditOpen] = useState(false);
  const [mutationPending, setMutationPending] = useState(false);
  const editButtonRef = useRef<HTMLButtonElement>(null);
  const editPanelId = `manual-operation-edit-panel-${operation.id}`;

  function closeEdit() {
    setEditOpen(false);
    queueMicrotask(() => editButtonRef.current?.focus());
  }
  return (
    <WorkbenchRow
      aside={
        operation.canEdit ||
        operation.canCancel ||
        operation.canRestore ||
        operation.canDelete ? (
          <div className={styles.rowActions}>
            {operation.canEdit ? (
              <Button
                aria-controls={editPanelId}
                aria-expanded={editOpen}
                disabled={mutationPending}
                onClick={() => setEditOpen((current) => !current)}
                ref={editButtonRef}
                tone="secondary"
              >
                Исправить
              </Button>
            ) : null}
            {operation.canCancel || operation.canRestore ? (
              <ManualOperationLifecycle
                action={operation.canCancel ? "cancel" : "restore"}
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
          </div>
        ) : undefined
      }
      date={operation.date}
      description={operation.description}
      id={operation.anchorId}
      expansion={
        operation.canEdit ? (
          <ManualOperationEdit
            csrfToken={csrfToken}
            disabled={mutationPending}
            isOpen={editOpen}
            onClose={closeEdit}
            onPendingChange={setMutationPending}
            {...(onOperationUpdated === undefined
              ? {}
              : { onUpdated: onOperationUpdated })}
            operationId={operation.id}
          />
        ) : undefined
      }
      expansionHidden={!editOpen}
      meta={
        <>
          <Badge tone={operation.operationTone}>
            {operation.operationLabel}
          </Badge>
          <Badge tone={operation.statusTone}>{operation.statusLabel}</Badge>
          {operation.meta.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </>
      }
      state={isTargeted ? "target" : "default"}
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
