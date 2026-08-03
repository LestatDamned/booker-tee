import { useMemo, useState } from "react";
import type { NavigateFunction } from "react-router";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { useToastQueue } from "../../ui/toast/toast";
import {
  seedDefaultTransactionRules,
  type TransactionRuleDirectoryDto,
  type TransactionRuleSummaryDto,
} from "./api/transaction-rules-api";
import { transactionRulePageUrl } from "./transaction-rule-list-query";

export function useTransactionRuleMutations({
  csrfToken,
  directory,
  navigate,
  onReload,
  pathname,
  search,
}: {
  csrfToken: string;
  directory: TransactionRuleDirectoryDto;
  navigate: NavigateFunction;
  onReload?: () => void;
  pathname: string;
  search: string;
}) {
  const [createdRules, setCreatedRules] = useState<TransactionRuleSummaryDto[]>(
    [],
  );
  const [updatedRules, setUpdatedRules] = useState<TransactionRuleSummaryDto[]>(
    [],
  );
  const [deletedRules, setDeletedRules] = useState<TransactionRuleSummaryDto[]>(
    [],
  );
  const [createOpen, setCreateOpen] = useState(false);
  const [seedConfirmOpen, setSeedConfirmOpen] = useState(false);
  const [seedPending, setSeedPending] = useState(false);
  const [seedError, setSeedError] = useState<string | null>(null);
  const snapshot = useMemo(
    () =>
      directoryWithLocalRules(
        directory,
        createdRules,
        updatedRules,
        deletedRules,
      ),
    [createdRules, deletedRules, directory, updatedRules],
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
    if (redirectIfUnauthenticated(result)) return;
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

  function ruleDeleted(item: TransactionRuleSummaryDto) {
    setDeletedRules((current) => [
      item,
      ...current.filter((rule) => rule.id !== item.id),
    ]);
    if (snapshot.items.length === 1 && snapshot.page.page > 1) {
      void navigate(transactionRulePageUrl(search, snapshot.page.page - 1), {
        replace: true,
      });
    }
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
    ruleDeleted,
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
  deletedRules: TransactionRuleSummaryDto[],
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
  const deletedIds = new Set(deletedRules.map((item) => item.id));
  const countedSourceIds = new Set([
    ...directory.items.map((item) => item.id),
    ...additions.map((item) => item.id),
  ]);
  const deletedCounted = deletedRules.filter((item) =>
    countedSourceIds.has(item.id),
  );
  const deletedActive = deletedCounted.filter((item) => item.isActive).length;
  const deletedVisible = [...visibleAdditions, ...items].filter((item) =>
    deletedIds.has(item.id),
  ).length;
  const normalizedTotal = Math.max(0, total - deletedVisible);
  const totalPages = Math.max(
    1,
    Math.ceil(normalizedTotal / directory.page.pageSize),
  );
  return {
    ...directory,
    items: [...visibleAdditions, ...items].filter(
      (item) => !deletedIds.has(item.id),
    ),
    counts: {
      all: directory.counts.all + additions.length - deletedCounted.length,
      active:
        directory.counts.active + activeAdditions + activeDelta - deletedActive,
      disabled:
        directory.counts.disabled +
        additions.length -
        activeAdditions +
        disabledDelta -
        (deletedCounted.length - deletedActive),
    },
    page: {
      ...directory.page,
      total: normalizedTotal,
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
