import { useState } from "react";

import { Button } from "../../../ui/button/button";
import { InlineNotice } from "../../../ui/inline-notice/inline-notice";
import type { ManualOperationDto } from "../api/manual-ledger-api";
import {
  changeManualOperationLifecycle,
  type ManualOperationLifecycleAction,
} from "../api/manual-ledger-mutations";
import styles from "../manual-ledger.module.css";

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
        icon="undo"
      >
        {actionLabels[action]}
      </Button>
      {state.status === "conflict" || state.status === "error" ? (
        <InlineNotice
          action={
            state.status === "conflict" && onRefresh ? (
              <Button icon="retry" onClick={refresh} tone="secondary">
                Обновить строку
              </Button>
            ) : state.status === "error" ? (
              <Button
                icon="retry"
                onClick={() => void changeStatus()}
                tone="secondary"
              >
                Повторить
              </Button>
            ) : undefined
          }
          layout="stacked"
          role="alert"
          title={
            state.status === "conflict"
              ? "Операция уже была изменена"
              : "Не удалось выполнить действие"
          }
          tone="danger"
        >
          {state.message}
        </InlineNotice>
      ) : null}
    </div>
  );
}
