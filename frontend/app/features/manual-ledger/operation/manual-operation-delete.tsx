import { useState } from "react";

import { Button } from "../../../ui/button/button";
import { FormError } from "../../../ui/field/form-error";
import { deleteManualOperation } from "../api/manual-ledger-mutations";
import styles from "../manual-ledger.module.css";

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

  if (state.status === "idle") {
    return (
      <Button
        disabled={disabled}
        onClick={() => setState({ status: "confirming" })}
        tone="danger"
        icon="delete"
      >
        Удалить окончательно
      </Button>
    );
  }

  if (state.status === "conflict" || state.status === "error") {
    return (
      <div className={styles.deleteConfirmation}>
        <FormError announce>{state.message}</FormError>
        {state.status === "conflict" && onRefresh ? (
          <Button icon="retry" onClick={refresh} tone="ghost">
            Обновить строку
          </Button>
        ) : (
          <Button
            icon="retry"
            onClick={() => setState({ status: "idle" })}
            tone="ghost"
          >
            Повторить
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className={styles.deleteConfirmation}>
      <p>
        Удалить операцию без возможности восстановления? Финансовая запись
        исчезнет.
      </p>
      <div className={styles.deleteActions}>
        <Button
          disabled={disabled}
          isLoading={state.status === "pending"}
          onClick={() => void confirmDelete()}
          tone="danger"
          icon="delete"
        >
          Да, удалить
        </Button>
        <Button
          disabled={disabled || state.status === "pending"}
          onClick={() => setState({ status: "idle" })}
          tone="ghost"
        >
          Не удалять
        </Button>
      </div>
    </div>
  );
}
