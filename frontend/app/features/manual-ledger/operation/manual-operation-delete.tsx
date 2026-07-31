import { useRef, useState } from "react";

import { Button } from "../../../ui/button/button";
import { ConfirmationDialog } from "../../../ui/confirmation-dialog/confirmation-dialog";
import { InlineNotice } from "../../../ui/inline-notice/inline-notice";
import { deleteManualOperation } from "../api/manual-ledger-mutations";

type ManualOperationDeleteProps = {
  csrfToken: string;
  disabled?: boolean;
  onDeleted?: (operationId: string) => void;
  onPendingChange?: (pending: boolean) => void;
  onRefresh?: () => void;
  operationId: string;
  version: number;
};

type DeleteState =
  | { status: "idle" | "confirming" | "pending" }
  | { status: "conflict" | "error"; message: string };

export function ManualOperationDelete({
  csrfToken,
  disabled = false,
  onDeleted,
  onPendingChange,
  onRefresh,
  operationId,
  version,
}: ManualOperationDeleteProps) {
  const [state, setState] = useState<DeleteState>({ status: "idle" });
  const deleteButtonRef = useRef<HTMLButtonElement>(null);

  async function confirmDelete() {
    if (disabled || state.status === "pending") {
      return;
    }
    setState({ status: "pending" });
    onPendingChange?.(true);
    const result = await deleteManualOperation(operationId, version, csrfToken);
    onPendingChange?.(false);
    if (result.status === "success") {
      onDeleted?.(operationId);
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/ledger/manual");
      return;
    }
    setState({ status: result.status, message: result.message });
  }

  function refresh() {
    setState({ status: "idle" });
    onRefresh?.();
  }

  const failed = state.status === "conflict" || state.status === "error";
  const dialogOpen =
    state.status === "confirming" || state.status === "pending";

  return (
    <>
      <Button
        disabled={disabled || state.status !== "idle"}
        icon="delete"
        onClick={() => setState({ status: "confirming" })}
        ref={deleteButtonRef}
        tone="danger"
      >
        Удалить окончательно
      </Button>
      {failed ? (
        <InlineNotice
          action={
            state.status === "conflict" && onRefresh ? (
              <Button icon="retry" onClick={refresh} tone="secondary">
                Обновить строку
              </Button>
            ) : (
              <Button
                icon="retry"
                onClick={() => setState({ status: "confirming" })}
                tone="secondary"
              >
                Повторить удаление
              </Button>
            )
          }
          layout="stacked"
          role="alert"
          title={
            state.status === "conflict"
              ? "Операция уже была изменена"
              : "Не удалось удалить операцию"
          }
          tone="danger"
        >
          {state.message}
        </InlineNotice>
      ) : null}
      {dialogOpen ? (
        <ConfirmationDialog
          cancelLabel="Не удалять"
          confirmLabel="Удалить навсегда"
          description="Финансовая запись исчезнет без возможности восстановления."
          disabled={disabled}
          onCancel={() => setState({ status: "idle" })}
          onConfirm={() => void confirmDelete()}
          pending={state.status === "pending"}
          returnFocusRef={deleteButtonRef}
          title="Удалить операцию?"
        />
      ) : null}
    </>
  );
}
