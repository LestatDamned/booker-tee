import { useRef, useState } from "react";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import {
  changeAccountLifecycle,
  type AccountLifecycleAction,
  type AccountSummaryDto,
} from "./api/accounts-api";

type AccountLifecycleFailure = {
  account: AccountSummaryDto;
  action: AccountLifecycleAction;
  message: string;
};

export function useAccountLifecycle({
  csrfToken,
  onCommitted,
  showToast,
}: {
  csrfToken: string;
  onCommitted: (account: AccountSummaryDto) => void;
  showToast: (toast: { message: string }) => void;
}) {
  const pendingRef = useRef(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [failure, setFailure] = useState<AccountLifecycleFailure | null>(null);
  const [archiveCandidate, setArchiveCandidate] =
    useState<AccountSummaryDto | null>(null);

  async function run(
    account: AccountSummaryDto,
    action: AccountLifecycleAction,
  ) {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPendingId(account.id);
    setFailure(null);
    const result = await changeAccountLifecycle({
      account,
      action,
      csrfToken,
    });
    pendingRef.current = false;
    setPendingId(null);
    if (result.status === "success") {
      onCommitted(result.account);
      setArchiveCandidate(null);
      showToast({
        message:
          action === "archive"
            ? `Счёт «${result.account.name}» перенесён в архив.`
            : `Счёт «${result.account.name}» восстановлен.`,
      });
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setArchiveCandidate(null);
    setFailure({ account, action, message: result.message });
  }

  return {
    archiveCandidate,
    cancelArchive: () => setArchiveCandidate(null),
    confirmArchive: () => {
      if (archiveCandidate) void run(archiveCandidate, "archive");
    },
    failure,
    pendingId,
    requestArchive: setArchiveCandidate,
    restore: (account: AccountSummaryDto) => void run(account, "restore"),
    retry: () => {
      if (failure) void run(failure.account, failure.action);
    },
  };
}
