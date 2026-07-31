import { useCallback, useEffect, useState } from "react";

import { IconButton } from "../button/icon-button";
import { Icon } from "../icon/icon";
import styles from "./toast.module.css";

export type ToastInput = {
  message: string;
  tone?: "success";
};

type ToastMessage = Required<ToastInput> & {
  id: number;
};

let nextToastId = 0;

export function useToastQueue() {
  const [queue, setQueue] = useState<ToastMessage[]>([]);

  const showToast = useCallback(({ message, tone = "success" }: ToastInput) => {
    setQueue((current) => [...current, { id: ++nextToastId, message, tone }]);
  }, []);

  const dismissToast = useCallback(() => {
    setQueue((current) => current.slice(1));
  }, []);

  return {
    dismissToast,
    showToast,
    toast: queue[0] ?? null,
  };
}

export function ToastViewport({
  duration = 6000,
  onDismiss,
  toast,
}: {
  duration?: number;
  onDismiss: () => void;
  toast: ToastMessage | null;
}) {
  if (!toast) return null;

  return (
    <div className={styles.viewport} data-toast-viewport>
      <ToastItem
        duration={duration}
        key={toast.id}
        onDismiss={onDismiss}
        toast={toast}
      />
    </div>
  );
}

function ToastItem({
  duration,
  onDismiss,
  toast,
}: {
  duration: number;
  onDismiss: () => void;
  toast: ToastMessage;
}) {
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    const timeout = window.setTimeout(onDismiss, duration);
    return () => window.clearTimeout(timeout);
  }, [duration, onDismiss, paused]);

  return (
    <div
      aria-atomic="true"
      className={styles.toast}
      data-tone={toast.tone}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setPaused(false);
        }
      }}
      onFocus={() => setPaused(true)}
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => setPaused(false)}
      role="status"
    >
      <Icon className={styles.icon} name="check" size={20} weight="fill" />
      <span className={styles.message}>{toast.message}</span>
      <IconButton
        aria-label="Закрыть уведомление"
        icon="close"
        onClick={onDismiss}
      />
    </div>
  );
}
