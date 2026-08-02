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
    setUpdatedRules((current) => [
      item,
      ...current.filter((rule) => rule.id !== item.id),
    ]);
    showToast({ message: `Правило «${item.name}» сохранено.` });
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
    ruleUpdated,
    seedConfirmOpen,
    seedDefaults,
    seedError,
    seedPending,
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
  const items = directory.items.map(
    (item) => replacements.get(item.id) ?? item,
  );
  const additions = createdRules.filter(
    (created) => !items.some((item) => item.id === created.id),
  );
  if (additions.length === 0) return { ...directory, items };
  const activeAdditions = additions.filter((item) => item.isActive).length;
  const total = directory.page.total + additions.length;
  const totalPages = Math.max(1, Math.ceil(total / directory.page.pageSize));
  return {
    ...directory,
    items: [...additions, ...items],
    counts: {
      all: directory.counts.all + additions.length,
      active: directory.counts.active + activeAdditions,
      disabled: directory.counts.disabled + additions.length - activeAdditions,
    },
    page: {
      ...directory.page,
      total,
      totalPages,
      hasNext: directory.page.page < totalPages,
    },
  };
}
