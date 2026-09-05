import { useRef, useState } from "react";

import { ActionStack } from "../../../ui/action-stack/action-stack";
import { Button, RouterButtonLink } from "../../../ui/button/button";
import { ExpansionPanel } from "../../../ui/expansion-panel/expansion-panel";
import { Icon } from "../../../ui/icon/icon";
import { MoneyValue } from "../../../ui/money-value/money-value";
import { StatusLabel } from "../../../ui/status-label/status-label";
import { Tag } from "../../../ui/tag/tag";
import { WorkbenchRow } from "../../../ui/workbench-row/workbench-row";
import {
  ImportedOperationCorrectionPanel,
  type ImportedOperationCorrectionPanelHandle,
} from "../../accounts/imported-operation-correction-panel";
import type { ManualOperationDto } from "../api/manual-ledger-api";
import type { ManualOperationRowModel } from "./manual-ledger-model";
import { ManualOperationDelete } from "./manual-operation-delete";
import { ManualOperationEdit } from "./manual-operation-edit";
import { ManualOperationLifecycle } from "./manual-operation-lifecycle";

type ManualOperationRowProps = {
  csrfToken: string;
  isEditing: boolean;
  isWorking: boolean;
  categories?: Array<{ id: string; name: string }>;
  properties?: Array<{ id: string; name: string }>;
  outsideCurrentSelection?: boolean;
  selected?: boolean;
  onDeleted?: (operationId: string) => void;
  onEdit: (operationId: string) => void;
  onEditClosed: () => void;
  onRefresh?: () => void;
  onOperationUpdated?: (operation: ManualOperationDto) => void;
  onSuccess?: (message: string) => void;
  onWorkStarted: () => void;
  operation: ManualOperationRowModel;
};

export function ManualOperationRow({
  csrfToken,
  categories = [],
  isEditing,
  isWorking,
  onDeleted,
  onEdit,
  onEditClosed,
  onRefresh,
  onOperationUpdated,
  onSuccess,
  onWorkStarted,
  operation,
  outsideCurrentSelection = false,
  properties = [],
  selected = false,
}: ManualOperationRowProps) {
  const [mutationPending, setMutationPending] = useState(false);
  const editButtonRef = useRef<HTMLButtonElement>(null);
  const importedPanelRef = useRef<ImportedOperationCorrectionPanelHandle>(null);
  const editPanelId = `operation-edit-panel-${operation.id}`;
  const importedEditable =
    operation.canEdit &&
    operation.editKind === "imported" &&
    operation.accountId !== null;
  const editable =
    (operation.canEdit && operation.editKind === "manual") || importedEditable;
  const sourceAction = operation.sourceTarget ? (
    <RouterButtonLink icon="source" to={operation.sourceTarget.url}>
      {operation.sourceTarget.label}
    </RouterButtonLink>
  ) : undefined;

  function closeEdit() {
    onEditClosed();
    queueMicrotask(() => editButtonRef.current?.focus());
  }

  function toggleEdit() {
    if (isEditing && operation.editKind === "imported") {
      importedPanelRef.current?.requestClose();
      return;
    }
    if (isEditing) closeEdit();
    else onEdit(operation.id);
  }

  return (
    <WorkbenchRow
      aside={
        editable ||
        operation.canCancel ||
        operation.canRestore ||
        operation.canDelete ||
        sourceAction ? (
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
                      onUpdated={(updated) => {
                        onOperationUpdated?.(updated);
                        onSuccess?.("Операция отменена.");
                      }}
                      operationId={operation.id}
                      version={operation.version}
                    />
                  ) : null}
                  {operation.canDelete ? (
                    <ManualOperationDelete
                      csrfToken={csrfToken}
                      disabled={mutationPending}
                      onDeleted={(operationId) => {
                        onDeleted?.(operationId);
                        onSuccess?.("Операция удалена.");
                      }}
                      onPendingChange={setMutationPending}
                      {...(onRefresh === undefined ? {} : { onRefresh })}
                      operationId={operation.id}
                      version={operation.version}
                    />
                  ) : null}
                </>
              ) : undefined
            }
            overflow={editable ? sourceAction : undefined}
            primary={
              editable ? (
                <Button
                  aria-controls={editPanelId}
                  aria-expanded={isEditing}
                  disabled={mutationPending}
                  onClick={toggleEdit}
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
                  onUpdated={(updated) => {
                    onOperationUpdated?.(updated);
                    onSuccess?.("Операция восстановлена.");
                  }}
                  operationId={operation.id}
                  version={operation.version}
                />
              ) : (
                sourceAction
              )
            }
          />
        ) : undefined
      }
      date={operation.date}
      description={operation.description}
      details={<OperationContext operation={operation} />}
      id={operation.anchorId}
      expansion={
        editable && isEditing ? (
          <ExpansionPanel
            id={editPanelId}
            title="Исправить операцию"
            titleId={`${editPanelId}-title`}
          >
            {operation.editKind === "imported" && operation.accountId ? (
              <ImportedOperationCorrectionPanel
                accountId={operation.accountId}
                categories={categories}
                csrfToken={csrfToken}
                onClose={closeEdit}
                onCommitted={() => {
                  closeEdit();
                  onRefresh?.();
                  onSuccess?.(
                    "Исправления импортированной операции сохранены.",
                  );
                }}
                operation={{
                  category: operation.category,
                  description: operation.description,
                  operationId: operation.id,
                  property: operation.property,
                  version: operation.version,
                }}
                properties={properties}
                ref={importedPanelRef}
              />
            ) : (
              <ManualOperationEdit
                csrfToken={csrfToken}
                disabled={mutationPending}
                onClose={closeEdit}
                onPendingChange={setMutationPending}
                onUpdated={(updated) => {
                  onOperationUpdated?.(updated);
                  onSuccess?.("Изменения операции сохранены.");
                }}
                operationId={operation.id}
              />
            )}
          </ExpansionPanel>
        ) : undefined
      }
      meta={<OperationMeta operation={operation} />}
      onAction={onWorkStarted}
      signals={
        outsideCurrentSelection || operation.readonlyReasonLabel ? (
          <>
            {outsideCurrentSelection ? (
              <StatusLabel tone="neutral">
                Операция открыта по прямой ссылке и не входит в текущую выборку.
              </StatusLabel>
            ) : null}
            {operation.readonlyReasonLabel ? (
              <StatusLabel tone="neutral">
                {operation.readonlyReasonLabel}
              </StatusLabel>
            ) : null}
          </>
        ) : undefined
      }
      state={isWorking ? "working" : selected ? "target" : "default"}
      {...(selected ? { tabIndex: -1 } : {})}
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

function OperationContext({
  operation,
}: {
  operation: ManualOperationRowModel;
}) {
  const account =
    operation.transferRouteLabel ?? operation.accountLabel ?? "Счёт не указан";
  return operation.source === "debt" ? (
    <>{account}</>
  ) : (
    <>
      {account} · {operation.sourceLabel ?? "Вручную"}
    </>
  );
}

function OperationMeta({ operation }: { operation: ManualOperationRowModel }) {
  const problemStatus =
    operation.statusTone === "warning" || operation.statusTone === "danger";
  return (
    <>
      <Tag tone={operation.operationTone}>{operation.operationLabel}</Tag>
      {operation.source === "debt" ? (
        <Tag tone="neutral" variant="soft">
          <Icon name="debts" />
          Долг
        </Tag>
      ) : null}
      {operation.transferRouteLabel ? null : (
        <>
          {operation.categoryLabel ? (
            <Tag tone="category">{operation.categoryLabel}</Tag>
          ) : (
            <Tag tone="neutral">Без категории</Tag>
          )}
          {operation.propertyLabel ? (
            <span>Объект: {operation.propertyLabel}</span>
          ) : null}
        </>
      )}
      {operation.status !== "confirmed" ? (
        <StatusLabel
          tone={operation.statusTone}
          variant={problemStatus ? "soft" : "plain"}
        >
          {operation.statusLabel}
        </StatusLabel>
      ) : null}
    </>
  );
}
