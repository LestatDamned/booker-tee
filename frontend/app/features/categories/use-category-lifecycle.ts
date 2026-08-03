import { useRef, useState } from "react";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import {
  changeCategoryLifecycle,
  deleteCategory,
  loadCategoryDetail,
  type CategoryDetailDto,
  type CategoryLifecycleAction,
} from "./api/category-detail-api";

type CategorySummary = CategoryDetailDto["category"];
type CategoryMutationAction = CategoryLifecycleAction | "delete";

export type CategoryLifecycleFailure = {
  action: CategoryMutationAction;
  blocked: boolean;
  category: CategorySummary;
  conflict: boolean;
  message: string;
};

export function useCategoryLifecycle({
  apiSearch,
  csrfToken,
  onCommitted,
  onDeleted,
  onReloaded,
  showToast,
}: {
  apiSearch: string;
  csrfToken: string;
  onCommitted: (category: CategorySummary) => void;
  onDeleted: (name: string) => void;
  onReloaded: (detail: CategoryDetailDto) => void;
  showToast: (toast: { message: string }) => void;
}) {
  const pendingRef = useRef(false);
  const [archiveCandidate, setArchiveCandidate] =
    useState<CategorySummary | null>(null);
  const [deleteCandidate, setDeleteCandidate] =
    useState<CategorySummary | null>(null);
  const [failure, setFailure] = useState<CategoryLifecycleFailure | null>(null);
  const [pending, setPending] = useState(false);

  async function run(
    category: CategorySummary,
    action: CategoryMutationAction,
  ) {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    setFailure(null);
    const result =
      action === "delete"
        ? await deleteCategory({ category, csrfToken })
        : await changeCategoryLifecycle({ action, category, csrfToken });
    pendingRef.current = false;
    setPending(false);
    setArchiveCandidate(null);
    setDeleteCandidate(null);

    if (result.status === "success") {
      if ("deletedId" in result) {
        onDeleted(result.name);
        return;
      }
      onCommitted(result.category);
      showToast({
        message:
          action === "archive"
            ? `Категория «${result.category.name}» перенесена в архив. История сохранена.`
            : `Категория «${result.category.name}» восстановлена.`,
      });
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setFailure({
      action,
      blocked: result.status === "blocked",
      category,
      conflict: result.status === "conflict",
      message: result.message,
    });
  }

  async function refreshAndRetry() {
    if (!failure || pendingRef.current) return;
    const retry = failure;
    pendingRef.current = true;
    setPending(true);
    const result = await loadCategoryDetail(retry.category.id, apiSearch);
    pendingRef.current = false;
    setPending(false);
    if (redirectIfUnauthenticated(result)) return;
    if (result.status !== "success") {
      setFailure({
        ...retry,
        conflict: false,
        message:
          result.status === "not_found"
            ? "Категория больше не доступна."
            : result.message,
      });
      return;
    }
    onReloaded(result.detail);
    const fresh = result.detail.category;
    if (!canRun(fresh, retry.action)) {
      setFailure(null);
      showToast({ message: "Категория обновлена до актуального состояния." });
      return;
    }
    setFailure(null);
    await run(fresh, retry.action);
  }

  return {
    archiveCandidate,
    cancelArchive: () => setArchiveCandidate(null),
    cancelDelete: () => setDeleteCandidate(null),
    confirmArchive: () => {
      if (archiveCandidate) void run(archiveCandidate, "archive");
    },
    confirmDelete: () => {
      if (deleteCandidate) void run(deleteCandidate, "delete");
    },
    deleteCandidate,
    failure,
    pending,
    refreshAndRetry,
    requestArchive: setArchiveCandidate,
    requestDelete: setDeleteCandidate,
    restore: (category: CategorySummary) => void run(category, "restore"),
    retry: () => {
      if (failure) void run(failure.category, failure.action);
    },
  };
}

function canRun(category: CategorySummary, action: CategoryMutationAction) {
  if (action === "archive") return category.capabilities.canArchive;
  if (action === "restore") return category.capabilities.canRestore;
  return category.capabilities.canDelete;
}
