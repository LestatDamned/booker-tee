import { useEffect, useRef, useState } from "react";

export function useImportReviewActionFeedback<TRecovery>() {
  const [error, setError] = useState<string | null>(null);
  const [recovery, setRecovery] = useState<TRecovery | null>(null);
  const alertRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (error) alertRef.current?.focus();
  }, [error]);

  function clearFeedback() {
    setError(null);
    setRecovery(null);
  }

  function showFailure(message: string, nextRecovery: TRecovery | null = null) {
    setError(message);
    setRecovery(nextRecovery);
  }

  return {
    alertRef,
    clearFeedback,
    error,
    recovery,
    showFailure,
  };
}
