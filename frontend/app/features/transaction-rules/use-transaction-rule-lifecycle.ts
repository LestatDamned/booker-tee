import { useRef, useState } from "react";

import {
  changeTransactionRuleLifecycle,
  loadTransactionRuleForEdit,
  type TransactionRuleSummaryDto,
} from "./api/transaction-rules-api";

export type TransactionRuleLifecycleAction = "enable" | "disable";

export type TransactionRuleLifecycleFailure = {
  action: TransactionRuleLifecycleAction;
  blocked: boolean;
  conflict: boolean;
  item: TransactionRuleSummaryDto;
  message: string;
};

export function useTransactionRuleLifecycle({
  csrfToken,
  onCommitted,
  showToast,
}: {
  csrfToken: string;
  onCommitted: (item: TransactionRuleSummaryDto) => void;
  showToast: (toast: { message: string }) => void;
}) {
  const pendingRef = useRef(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [failure, setFailure] =
    useState<TransactionRuleLifecycleFailure | null>(null);

  async function run(
    item: TransactionRuleSummaryDto,
    action: TransactionRuleLifecycleAction,
  ) {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPendingId(item.id);
    setFailure(null);
    const result = await changeTransactionRuleLifecycle(
      item,
      action,
      csrfToken,
    );
    pendingRef.current = false;
    setPendingId(null);
    if (result.status === "success") {
      onCommitted(result.value.item);
      const count = result.value.impact.existingSuggestionCount;
      showToast({
        message:
          action === "disable"
            ? `Правило «${result.value.item.name}» выключено. Новые операции больше не сопоставляются; ${suggestionCount(count)} сохранено.`
            : `Правило «${result.value.item.name}» включено для будущих операций; ${suggestionCount(count)} не изменено.`,
      });
      return;
    }
    setFailure({
      action,
      blocked: result.status === "blocked",
      conflict: result.status === "conflict",
      item,
      message: result.message,
    });
  }

  async function refreshAndRetry() {
    if (!failure || pendingRef.current) return;
    const retry = failure;
    pendingRef.current = true;
    setPendingId(retry.item.id);
    const loaded = await loadTransactionRuleForEdit(retry.item.id);
    pendingRef.current = false;
    setPendingId(null);
    if (loaded.status !== "success") {
      setFailure({ ...retry, conflict: false, message: loaded.message });
      return;
    }
    const fresh = loaded.value.item;
    onCommitted(fresh);
    if (!canRun(fresh, retry.action)) {
      setFailure(null);
      showToast({ message: "Правило обновлено до актуального состояния." });
      return;
    }
    setFailure(null);
    await run(fresh, retry.action);
  }

  function explainBlocked(item: TransactionRuleSummaryDto) {
    setFailure({
      action: "enable",
      blocked: true,
      conflict: false,
      item,
      message: enableBlockerMessage(item.capabilities.enableBlockedReasonCode),
    });
  }

  return {
    clearFailure: () => setFailure(null),
    disable: (item: TransactionRuleSummaryDto) => void run(item, "disable"),
    enable: (item: TransactionRuleSummaryDto) => void run(item, "enable"),
    explainBlocked,
    failure,
    pendingId,
    refreshAndRetry,
    retry: () => {
      if (failure) void run(failure.item, failure.action);
    },
  };
}

function canRun(
  item: TransactionRuleSummaryDto,
  action: TransactionRuleLifecycleAction,
): boolean {
  return action === "enable"
    ? item.capabilities.canEnable
    : item.capabilities.canDisable;
}

function enableBlockerMessage(
  reason: TransactionRuleSummaryDto["capabilities"]["enableBlockedReasonCode"],
): string {
  if (reason === "category_inactive")
    return "Сначала выберите активную категорию в редакторе правила.";
  if (reason === "property_archived")
    return "Сначала выберите активный объект или уберите объект из правила.";
  if (reason === "account_unavailable")
    return "Связанный счёт недоступен. Исправьте цель правила перед включением.";
  return "Обновите правило и устраните недоступную цель перед включением.";
}

function suggestionCount(count: number): string {
  const word =
    count % 10 === 1 && count % 100 !== 11
      ? "существующее предложение"
      : "существующих предложений";
  return `${count} ${word}`;
}
