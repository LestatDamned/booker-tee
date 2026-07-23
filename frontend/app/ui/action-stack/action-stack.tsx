import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { Icon } from "../icon/icon";
import styles from "./action-stack.module.css";

const ACTION_MENU_OPEN_EVENT = "booker:action-menu-open";

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
  const instanceId = useId();
  const menuId = useId();
  const open = disclosureOpen ?? internalOpen;

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

  function toggleMenu() {
    const nextOpen = !open;
    if (nextOpen) {
      const triggerRect = triggerRef.current?.getBoundingClientRect();
      if (triggerRect) {
        setMenuPosition({
          left: Math.max(8, triggerRect.left),
          top: triggerRect.bottom + 8,
          width: Math.min(triggerRect.width, window.innerWidth - 16),
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
        left: Math.max(viewportInset, triggerRect.left),
        top: Math.max(
          viewportInset,
          Math.min(
            proposedTop,
            window.innerHeight - menuHeight - viewportInset,
          ),
        ),
        width: Math.min(
          triggerRect.width,
          window.innerWidth - viewportInset * 2,
        ),
      });
    }

    positionMenu();
    window.addEventListener("resize", positionMenu);
    window.addEventListener("scroll", positionMenu, true);
    return () => {
      window.removeEventListener("resize", positionMenu);
      window.removeEventListener("scroll", positionMenu, true);
    };
  }, [open, danger, overflow]);

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
