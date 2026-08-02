import { useMemo, useState } from "react";
import type { NavigateFunction } from "react-router";

import { useToastQueue } from "../../ui/toast/toast";
import {
  seedDefaultTransactionRules,
  type TransactionRuleDirectoryDto,
  type TransactionRuleSummaryDto,
} from "./api/transaction-rules-api";

export function useTransactionRuleMutations({
  csrfToken,
  directory,
  navigate,
  onReload,
  pathname,
}: {
  csrfToken: string;
  directory: TransactionRuleDirectoryDto;
  navigate: NavigateFunction;
  onReload?: () => void;
  pathname: string;
}) {
  const [createdRules, setCreatedRules] = useState<TransactionRuleSummaryDto[]>(
    [],
  );
  const [updatedRules, setUpdatedRules] = useState<TransactionRuleSummaryDto[]>(
    [],
  );
  const [createOpen, setCreateOpen] = useState(false);
  const [seedConfirmOpen, setSeedConfirmOpen] = useState(false);
  const [seedPending, setSeedPending] = useState(false);
  const [seedError, setSeedError] = useState<string | null>(null);
  const snapshot = useMemo(
    () => directoryWithLocalRules(directory, createdRules, updatedRules),
    [createdRules, directory, updatedRules],
  );
  const { dismissToast, showToast, toast } = useToastQueue();

  function ruleCreated(item: TransactionRuleSummaryDto) {
    setCreatedRules((current) => [
      item,
      ...current.filter((rule) => rule.id !== item.id),
    ]);
    setCreateOpen(false);
    showToast({ message: `Правило «${item.name}» создано.` });
    void navigate({ pathname, hash: `#rule-${item.id}` });
    onReload?.();
  }

  async function seedDefaults() {
    setSeedPending(true);
    setSeedError(null);
    const result = await seedDefaultTransactionRules(csrfToken);
    setSeedPending(false);
    if (result.status !== "success") {
      setSeedError(result.message);
      return;
    }
    setSeedConfirmOpen(false);
    showToast({
      message: `Базовые правила: создано ${result.value.createdRules}, уже было ${result.value.existingRules}, новых категорий ${result.value.createdCategories}.`,
    });
    onReload?.();
  }

  function ruleUpdated(item: TransactionRuleSummaryDto) {
    ruleReplaced(item);
    showToast({ message: `Правило «${item.name}» сохранено.` });
  }

  function ruleReplaced(item: TransactionRuleSummaryDto) {
    setUpdatedRules((current) => [
      item,
      ...current.filter((rule) => rule.id !== item.id),
    ]);
    onReload?.();
  }

  return {
    closeCreate: () => setCreateOpen(false),
    closeSeed: () => setSeedConfirmOpen(false),
    createOpen,
    dismissToast,
    openCreate: () => setCreateOpen(true),
    openSeed: () => {
      setSeedError(null);
      setSeedConfirmOpen(true);
    },
    ruleCreated,
    ruleReplaced,
    ruleUpdated,
    seedConfirmOpen,
    seedDefaults,
    seedError,
    seedPending,
    showToast,
    snapshot,
    toast,
  };
}

function directoryWithLocalRules(
  directory: TransactionRuleDirectoryDto,
  createdRules: TransactionRuleSummaryDto[],
  updatedRules: TransactionRuleSummaryDto[],
): TransactionRuleDirectoryDto {
  const replacements = new Map(updatedRules.map((item) => [item.id, item]));
  let activeDelta = 0;
  let disabledDelta = 0;
  let visibilityDelta = 0;
  const items = directory.items.flatMap((item) => {
    const replacement = replacements.get(item.id);
    if (!replacement) return [item];
    if (replacement.isActive !== item.isActive) {
      activeDelta += replacement.isActive ? 1 : -1;
      disabledDelta += replacement.isActive ? -1 : 1;
      const wasVisible = matchesStatus(item, directory.appliedFilters.status);
      const isVisible = matchesStatus(
        replacement,
        directory.appliedFilters.status,
      );
      visibilityDelta += Number(isVisible) - Number(wasVisible);
    }
    return matchesStatus(replacement, directory.appliedFilters.status)
      ? [replacement]
      : [];
  });
  const additions = createdRules
    .filter(
      (created) => !directory.items.some((item) => item.id === created.id),
    )
    .map((created) => replacements.get(created.id) ?? created);
  const activeAdditions = additions.filter((item) => item.isActive).length;
  const visibleAdditions = additions.filter((item) =>
    matchesStatus(item, directory.appliedFilters.status),
  );
  const total =
    directory.page.total + visibilityDelta + visibleAdditions.length;
  const totalPages = Math.max(1, Math.ceil(total / directory.page.pageSize));
  return {
    ...directory,
    items: [...visibleAdditions, ...items],
    counts: {
      all: directory.counts.all + additions.length,
      active: directory.counts.active + activeAdditions + activeDelta,
      disabled:
        directory.counts.disabled +
        additions.length -
        activeAdditions +
        disabledDelta,
    },
    page: {
      ...directory.page,
      total,
      totalPages,
      hasNext: directory.page.page < totalPages,
    },
  };
}

function matchesStatus(
  item: TransactionRuleSummaryDto,
  status: TransactionRuleDirectoryDto["appliedFilters"]["status"],
): boolean {
  if (status === "active") return item.isActive;
  if (status === "disabled") return !item.isActive;
  return true;
}
