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
  const [createOpen, setCreateOpen] = useState(false);
  const [seedConfirmOpen, setSeedConfirmOpen] = useState(false);
  const [seedPending, setSeedPending] = useState(false);
  const [seedError, setSeedError] = useState<string | null>(null);
  const snapshot = useMemo(
    () => directoryWithCreatedRules(directory, createdRules),
    [createdRules, directory],
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
    seedConfirmOpen,
    seedDefaults,
    seedError,
    seedPending,
    snapshot,
    toast,
  };
}

function directoryWithCreatedRules(
  directory: TransactionRuleDirectoryDto,
  createdRules: TransactionRuleSummaryDto[],
): TransactionRuleDirectoryDto {
  const additions = createdRules.filter(
    (created) => !directory.items.some((item) => item.id === created.id),
  );
  if (additions.length === 0) return directory;
  const activeAdditions = additions.filter((item) => item.isActive).length;
  const total = directory.page.total + additions.length;
  const totalPages = Math.max(1, Math.ceil(total / directory.page.pageSize));
  return {
    ...directory,
    items: [...additions, ...directory.items],
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
