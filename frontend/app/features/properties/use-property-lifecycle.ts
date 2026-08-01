import { useRef, useState } from "react";

import type {
  PropertyLifecycleAction,
  PropertySummaryDto,
} from "./api/properties-api";
import { changePropertyLifecycle, loadProperties } from "./api/properties-api";

export type PropertyLifecycleFailure = {
  action: PropertyLifecycleAction;
  conflict: boolean;
  message: string;
  property: PropertySummaryDto;
};

export function usePropertyLifecycle({
  csrfToken,
  onCommitted,
  onReloaded,
  showToast,
}: {
  csrfToken: string;
  onCommitted: (property: PropertySummaryDto) => void;
  onReloaded: (properties: PropertySummaryDto[]) => void;
  showToast: (toast: { message: string }) => void;
}) {
  const pendingRef = useRef<string | null>(null);
  const [archiveCandidate, setArchiveCandidate] =
    useState<PropertySummaryDto | null>(null);
  const [failure, setFailure] = useState<PropertyLifecycleFailure | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  async function run(
    property: PropertySummaryDto,
    action: PropertyLifecycleAction,
  ) {
    if (pendingRef.current) return;
    pendingRef.current = property.id;
    setPendingId(property.id);
    setFailure(null);
    const result = await changePropertyLifecycle({
      action,
      csrfToken,
      property,
    });
    pendingRef.current = null;
    setPendingId(null);
    if (result.status === "success") {
      onCommitted(result.property);
      setArchiveCandidate(null);
      showToast({
        message:
          action === "archive"
            ? `Объект «${result.property.name}» перенесён в архив. История сохранена.`
            : `Объект «${result.property.name}» восстановлен.`,
      });
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/properties");
      return;
    }
    setArchiveCandidate(null);
    setFailure({
      action,
      conflict: result.status === "conflict",
      message: result.message,
      property,
    });
  }

  async function refreshAndRetry() {
    if (!failure || pendingRef.current) return;
    const retry = failure;
    pendingRef.current = retry.property.id;
    setPendingId(retry.property.id);
    const result = await loadProperties();
    pendingRef.current = null;
    setPendingId(null);
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/properties");
      return;
    }
    if (result.status === "error") {
      setFailure({ ...retry, message: result.message });
      return;
    }
    onReloaded(result.directory.items);
    const fresh = result.directory.items.find(
      (property) => property.id === retry.property.id,
    );
    if (!fresh) {
      setFailure({
        ...retry,
        conflict: false,
        message: "Объект больше не доступен.",
      });
      return;
    }
    const canRetry =
      retry.action === "archive"
        ? fresh.capabilities.canArchive
        : fresh.capabilities.canRestore;
    if (!canRetry) {
      setFailure(null);
      showToast({
        message: "Список объектов обновлён до актуального состояния.",
      });
      return;
    }
    setFailure(null);
    await run(fresh, retry.action);
  }

  return {
    archiveCandidate,
    cancelArchive: () => setArchiveCandidate(null),
    confirmArchive: () => {
      if (archiveCandidate) void run(archiveCandidate, "archive");
    },
    failure,
    pendingId,
    refreshAndRetry,
    requestArchive: setArchiveCandidate,
    restore: (property: PropertySummaryDto) => void run(property, "restore"),
    retry: () => {
      if (failure) void run(failure.property, failure.action);
    },
  };
}
