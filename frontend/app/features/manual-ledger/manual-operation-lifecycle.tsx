import { useState } from "react";

import { Button } from "../../ui/button/button";
import { FormError } from "../../ui/field/form-error";
import type { ManualOperationDto } from "./manual-ledger-api";
import {
  changeManualOperationLifecycle,
  type ManualOperationLifecycleAction,
} from "./manual-ledger-mutations";
import styles from "./manual-ledger.module.css";

type ManualOperationLifecycleProps = {
  action: ManualOperationLifecycleAction;
  csrfToken: string;
  disabled?: boolean;
  onPendingChange?: (pending: boolean) => void;
  onRefresh?: () => void;
  onUpdated?: (operation: ManualOperationDto) => void;
  operationId: string;
  version: number;
};

type LifecycleState =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "conflict" | "error"; message: string };

const actionLabels: Record<ManualOperationLifecycleAction, string> = {
  cancel: "Отменить операцию",
  restore: "Восстановить операцию",
};

export function ManualOperationLifecycle({
  action,
  csrfToken,
  disabled = false,
  onPendingChange,
  onRefresh,
  onUpdated,
  operationId,
  version,
}: ManualOperationLifecycleProps) {
  const [state, setState] = useState<LifecycleState>({ status: "idle" });

  async function changeStatus() {
    if (disabled || state.status === "pending") {
      return;
    }
    setState({ status: "pending" });
    onPendingChange?.(true);
    const result = await changeManualOperationLifecycle(
      operationId,
      action,
      version,
      csrfToken,
    );
    onPendingChange?.(false);
    if (result.status === "success") {
      setState({ status: "idle" });
      onUpdated?.(result.operation);
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/ledger/manual");
      return;
    }
    setState({
      status: result.status === "conflict" ? "conflict" : "error",
      message: result.message,
    });
  }

  function refresh() {
    setState({ status: "idle" });
    onRefresh?.();
  }

  return (
    <div className={styles.lifecycleAction}>
      <Button
        disabled={disabled}
        isLoading={state.status === "pending"}
        onClick={() => void changeStatus()}
        tone={action === "restore" ? "primary" : "dangerSecondary"}
      >
        {actionLabels[action]}
      </Button>
      {state.status === "conflict" || state.status === "error" ? (
        <div className={styles.lifecycleFeedback}>
          <FormError announce>{state.message}</FormError>
          {state.status === "conflict" && onRefresh ? (
            <Button onClick={refresh} tone="ghost">
              Обновить строку
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
