import { useRef, useState } from "react";

import type { CategorySummaryDto } from "./api/categories-api";
import { loadCategories } from "./api/categories-api";
import {
  changeCategoryLifecycle,
  type CategoryLifecycleAction,
} from "./api/category-detail-api";

export type CategoryDirectoryLifecycleFailure = {
  action: CategoryLifecycleAction;
  category: CategorySummaryDto;
  conflict: boolean;
  message: string;
};

export function useCategoryDirectoryLifecycle({
  csrfToken,
  onCommitted,
  onReloaded,
  showToast,
}: {
  csrfToken: string;
  onCommitted: (category: CategorySummaryDto) => void;
  onReloaded: (categories: CategorySummaryDto[]) => void;
  showToast: (toast: { message: string }) => void;
}) {
  const pendingRef = useRef<string | null>(null);
  const [archiveCandidate, setArchiveCandidate] =
    useState<CategorySummaryDto | null>(null);
  const [archiveBlocker, setArchiveBlocker] =
    useState<CategorySummaryDto | null>(null);
  const [failure, setFailure] =
    useState<CategoryDirectoryLifecycleFailure | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  async function run(
    category: CategorySummaryDto,
    action: CategoryLifecycleAction,
  ) {
    if (pendingRef.current) return;
    pendingRef.current = category.id;
    setPendingId(category.id);
    setFailure(null);
    setArchiveBlocker(null);
    const result = await changeCategoryLifecycle({
      action,
      category,
      csrfToken,
    });
    pendingRef.current = null;
    setPendingId(null);
    setArchiveCandidate(null);

    if (result.status === "success") {
      onCommitted(result.category);
      showToast({
        message:
          action === "archive"
            ? `Категория «${result.category.name}» перенесена в архив. История сохранена.`
            : `Категория «${result.category.name}» восстановлена.`,
      });
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/categories");
      return;
    }
    if (result.status === "blocked") {
      await reloadArchiveBlocker(category);
      return;
    }
    setFailure({
      action,
      category,
      conflict: result.status === "conflict",
      message: result.message,
    });
  }

  async function reloadArchiveBlocker(category: CategorySummaryDto) {
    const result = await loadCategories();
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/categories");
      return;
    }
    if (result.status === "error") {
      setArchiveBlocker(category);
      return;
    }
    onReloaded(result.directory.items);
    setArchiveBlocker(
      result.directory.items.find((item) => item.id === category.id) ??
        category,
    );
  }

  async function refreshAndRetry() {
    if (!failure || pendingRef.current) return;
    const retry = failure;
    pendingRef.current = retry.category.id;
    setPendingId(retry.category.id);
    const result = await loadCategories();
    pendingRef.current = null;
    setPendingId(null);
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/categories");
      return;
    }
    if (result.status === "error") {
      setFailure({ ...retry, message: result.message });
      return;
    }
    onReloaded(result.directory.items);
    const fresh = result.directory.items.find(
      (category) => category.id === retry.category.id,
    );
    if (!fresh) {
      setFailure({
        ...retry,
        conflict: false,
        message: "Категория больше не доступна.",
      });
      return;
    }
    if (!canRun(fresh, retry.action)) {
      setFailure(null);
      if (
        retry.action === "archive" &&
        fresh.capabilities.archiveBlockedReasonCode === "active_rules"
      ) {
        setArchiveBlocker(fresh);
      } else {
        showToast({
          message: "Список категорий обновлён до актуального состояния.",
        });
      }
      return;
    }
    setFailure(null);
    await run(fresh, retry.action);
  }

  function requestArchive(category: CategorySummaryDto) {
    setFailure(null);
    if (
      !category.capabilities.canArchive &&
      category.capabilities.archiveBlockedReasonCode === "active_rules"
    ) {
      setArchiveBlocker(category);
      return;
    }
    setArchiveBlocker(null);
    setArchiveCandidate(category);
  }

  return {
    archiveBlocker,
    archiveCandidate,
    cancelArchive: () => setArchiveCandidate(null),
    confirmArchive: () => {
      if (archiveCandidate) void run(archiveCandidate, "archive");
    },
    dismissArchiveBlocker: () => setArchiveBlocker(null),
    failure,
    pendingId,
    refreshAndRetry,
    requestArchive,
    restore: (category: CategorySummaryDto) => void run(category, "restore"),
    retry: () => {
      if (failure) void run(failure.category, failure.action);
    },
  };
}

function canRun(category: CategorySummaryDto, action: CategoryLifecycleAction) {
  return action === "archive"
    ? category.capabilities.canArchive
    : category.capabilities.canRestore;
}
