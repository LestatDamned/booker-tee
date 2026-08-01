import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { Icon } from "../icon/icon";
import styles from "./action-stack.module.css";

const ACTION_MENU_OPEN_EVENT = "booker:action-menu-open";

function horizontalMenuPosition(triggerRect: DOMRect, compact: boolean) {
  const viewportInset = 8;
  const availableWidth = window.innerWidth - viewportInset * 2;
  const width = compact
    ? Math.min(224, availableWidth)
    : Math.min(triggerRect.width, availableWidth);
  return {
    left: compact
      ? Math.max(
          viewportInset,
          Math.min(
            triggerRect.right - width,
            window.innerWidth - width - viewportInset,
          ),
        )
      : Math.max(viewportInset, triggerRect.left),
    width,
  };
}

type ActionStackProps = {
  danger?: ReactNode;
  disclosureOpen?: boolean;
  onDisclosureChange?: (open: boolean) => void;
  overflow?: ReactNode;
  primary?: ReactNode;
  secondary?: ReactNode;
  orientation?: "column" | "row";
};

export function ActionStack({
  danger,
  disclosureOpen,
  onDisclosureChange,
  overflow,
  primary,
  secondary,
  orientation = "column",
}: ActionStackProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState<CSSProperties | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const focusMenuOnOpenRef = useRef(false);
  const instanceId = useId();
  const menuId = useId();
  const open = disclosureOpen ?? internalOpen;
  const compactTrigger = orientation === "row";

  const setOpen = useCallback(
    (nextOpen: boolean, restoreFocus = false) => {
      if (disclosureOpen === undefined) setInternalOpen(nextOpen);
      onDisclosureChange?.(nextOpen);
      if (!nextOpen && restoreFocus) {
        queueMicrotask(() => triggerRef.current?.focus());
      }
    },
    [disclosureOpen, onDisclosureChange],
  );

  function toggleMenu(event: MouseEvent<HTMLButtonElement>) {
    const nextOpen = !open;
    if (nextOpen) {
      focusMenuOnOpenRef.current = event.detail === 0;
      const triggerRect = triggerRef.current?.getBoundingClientRect();
      if (triggerRect) {
        setMenuPosition({
          ...horizontalMenuPosition(triggerRect, compactTrigger),
          top: triggerRect.bottom + 8,
        });
      }
      window.dispatchEvent(
        new CustomEvent(ACTION_MENU_OPEN_EVENT, { detail: instanceId }),
      );
    }
    setOpen(nextOpen, !nextOpen);
  }

  useEffect(() => {
    function closeOtherMenu(event: Event) {
      if (event instanceof CustomEvent && event.detail !== instanceId && open) {
        setOpen(false);
      }
    }
    window.addEventListener(ACTION_MENU_OPEN_EVENT, closeOtherMenu);
    return () =>
      window.removeEventListener(ACTION_MENU_OPEN_EVENT, closeOtherMenu);
  }, [instanceId, open, setOpen]);

  useEffect(() => {
    if (!open) return;

    function closeOnPointerDown(event: PointerEvent) {
      const target = event.target;
      if (
        target instanceof Element &&
        (rootRef.current?.contains(target) ||
          menuRef.current?.contains(target) ||
          target.closest('[data-action-stack-overlay="true"]'))
      ) {
        return;
      }
      setOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false, true);
    }

    document.addEventListener("pointerdown", closeOnPointerDown);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnPointerDown);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open, setOpen]);

  useLayoutEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    if (!trigger) return;
    const triggerElement = trigger;

    function positionMenu() {
      const triggerRect = triggerElement.getBoundingClientRect();
      const menuHeight = menuRef.current?.getBoundingClientRect().height ?? 0;
      const viewportInset = 8;
      const gap = 8;
      const availableBelow = window.innerHeight - triggerRect.bottom;
      const availableAbove = triggerRect.top;
      const openAbove =
        availableBelow < menuHeight + gap && availableAbove > availableBelow;
      const proposedTop = openAbove
        ? triggerRect.top - menuHeight - gap
        : triggerRect.bottom + gap;
      setMenuPosition({
        ...horizontalMenuPosition(triggerRect, compactTrigger),
        top: Math.max(
          viewportInset,
          Math.min(
            proposedTop,
            window.innerHeight - menuHeight - viewportInset,
          ),
        ),
      });
    }

    positionMenu();
    if (focusMenuOnOpenRef.current) {
      focusMenuOnOpenRef.current = false;
      queueMicrotask(() =>
        menuRef.current
          ?.querySelector<HTMLElement>(
            "button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled)",
          )
          ?.focus(),
      );
    }
    window.addEventListener("resize", positionMenu);
    window.addEventListener("scroll", positionMenu, true);
    return () => {
      window.removeEventListener("resize", positionMenu);
      window.removeEventListener("scroll", positionMenu, true);
    };
  }, [open, danger, overflow, compactTrigger]);

  const actionMenu =
    open && typeof document !== "undefined"
      ? createPortal(
          <div
            aria-label="Дополнительные действия"
            className={styles.menu}
            id={menuId}
            ref={menuRef}
            style={menuPosition ?? undefined}
          >
            <div className={styles.menuBody}>
              {overflow ? <div className={styles.group}>{overflow}</div> : null}
              {danger ? (
                <div aria-label="Опасные действия" className={styles.danger}>
                  {danger}
                </div>
              ) : null}
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <div
      className={`${styles.stack} ${orientation === "row" ? styles.horizontal : ""}`}
      ref={rootRef}
    >
      {primary ? <div className={styles.group}>{primary}</div> : null}
      {secondary ? <div className={styles.group}>{secondary}</div> : null}
      {overflow || danger ? (
        <div className={styles.more}>
          <button
            aria-label="Ещё действия"
            aria-controls={menuId}
            aria-expanded={open}
            className={styles.trigger}
            onClick={toggleMenu}
            ref={triggerRef}
            type="button"
          >
            <Icon name="more" size={18} weight="bold" />
            <span>Ещё действия</span>
            <Icon
              className={styles.triggerCaret}
              name="expand"
              size={16}
              weight="bold"
            />
          </button>
          {actionMenu}
        </div>
      ) : null}
    </div>
  );
}
