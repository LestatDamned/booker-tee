import { Button } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type { TransactionRuleLifecycleFailure } from "./use-transaction-rule-lifecycle";

export function TransactionRuleLifecycleNotice({
  failure,
  onClear,
  onOpenEditor,
  onRefreshAndRetry,
  onRetry,
  pending,
}: {
  failure: TransactionRuleLifecycleFailure;
  onClear: () => void;
  onOpenEditor: (
    ruleId: string,
    variant: "desktop" | "mobile",
    trigger: HTMLButtonElement,
  ) => void;
  onRefreshAndRetry: () => void;
  onRetry: () => void;
  pending: boolean;
}) {
  return (
    <InlineNotice
      action={
        failure.blocked ? (
          <Button
            icon="edit"
            onClick={(event) => {
              const variant = window.matchMedia?.("(max-width: 64rem)").matches
                ? "mobile"
                : "desktop";
              onClear();
              onOpenEditor(failure.item.id, variant, event.currentTarget);
            }}
            tone="secondary"
          >
            Изменить правило
          </Button>
        ) : (
          <Button
            disabled={pending}
            icon="retry"
            isLoading={pending}
            onClick={failure.conflict ? onRefreshAndRetry : onRetry}
            tone="secondary"
          >
            {failure.conflict ? "Обновить и повторить" : "Повторить"}
          </Button>
        )
      }
      role="alert"
      title={
        failure.blocked
          ? "Правило пока нельзя включить"
          : "Не удалось изменить состояние правила"
      }
      tone={failure.blocked ? "warning" : "danger"}
    >
      {failure.message}
    </InlineNotice>
  );
}
