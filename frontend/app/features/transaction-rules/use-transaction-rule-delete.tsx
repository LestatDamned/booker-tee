import { useRef, useState } from "react";

import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import {
  deleteTransactionRule,
  loadTransactionRuleForEdit,
  type TransactionRuleSummaryDto,
} from "./api/transaction-rules-api";

export type TransactionRuleDeleteFailure = {
  blocked: boolean;
  conflict: boolean;
  item: TransactionRuleSummaryDto;
  message: string;
};

export function useTransactionRuleDelete({
  csrfToken,
  onDeleted,
  onReloaded,
  showToast,
}: {
  csrfToken: string;
  onDeleted: (item: TransactionRuleSummaryDto) => void;
  onReloaded: (item: TransactionRuleSummaryDto) => void;
  showToast: (toast: { message: string }) => void;
}) {
  const pendingRef = useRef(false);
  const [candidate, setCandidate] = useState<TransactionRuleSummaryDto | null>(
    null,
  );
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [failure, setFailure] = useState<TransactionRuleDeleteFailure | null>(
    null,
  );

  async function run(item: TransactionRuleSummaryDto) {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPendingId(item.id);
    setFailure(null);
    const result = await deleteTransactionRule(item, csrfToken);
    pendingRef.current = false;
    setPendingId(null);
    if (result.status === "success") {
      setCandidate(null);
      onDeleted(item);
      showToast({
        message: `Правило «${result.value.name}» удалено. Финансовые данные не изменены.`,
      });
      return;
    }
    setCandidate(null);
    setFailure({
      blocked: result.status === "blocked",
      conflict: result.status === "conflict",
      item,
      message:
        result.status === "blocked"
          ? deleteBlockerMessage(
              result.blockedReasonCode,
              result.directRawSuggestionCount,
            )
          : result.message,
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
    onReloaded(fresh);
    if (!fresh.capabilities.canDelete) {
      setFailure({
        blocked: true,
        conflict: false,
        item: fresh,
        message: deleteBlockerMessage(
          fresh.capabilities.deleteBlockedReasonCode,
          fresh.usage.directRawSuggestionCount,
        ),
      });
      return;
    }
    setFailure(null);
    await run(fresh);
  }

  function explainBlocked(item: TransactionRuleSummaryDto) {
    setFailure({
      blocked: true,
      conflict: false,
      item,
      message: deleteBlockerMessage(
        item.capabilities.deleteBlockedReasonCode,
        item.usage.directRawSuggestionCount,
      ),
    });
  }

  const dialog = candidate ? (
    <ConfirmationDialog
      confirmLabel="Удалить правило"
      description={`Правило «${candidate.name}» будет удалено без возможности восстановления. Это удалит только определение правила: источники импорта, review-предложения и подтверждённые операции не изменятся.`}
      onCancel={() => setCandidate(null)}
      onConfirm={() => void run(candidate)}
      pending={pendingId === candidate.id}
      title="Удалить правило?"
    />
  ) : null;

  return {
    clearFailure: () => setFailure(null),
    dialog,
    explainBlocked,
    failure,
    pendingId,
    refreshAndRetry,
    requestDelete: setCandidate,
    retry: () => {
      if (failure) void run(failure.item);
    },
  };
}

function deleteBlockerMessage(
  reason: TransactionRuleSummaryDto["capabilities"]["deleteBlockedReasonCode"],
  count: number,
): string {
  if (reason === "active_rule") {
    return "Сначала выключите правило. После этого сервер повторно проверит, использовалось ли оно в Import Review.";
  }
  if (reason === "raw_suggestions") {
    return `${suggestionCount(count)} хранит provenance этого правила. Удаление недоступно; правило можно оставить выключенным.`;
  }
  return "Правило больше нельзя удалить. Обновите список, чтобы увидеть актуальную причину.";
}

function suggestionCount(count: number): string {
  const word = count === 1 ? "review-предложение" : "review-предложений";
  return `${count} ${word}`;
}
