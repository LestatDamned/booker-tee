import {
  type AriaAttributes,
  type CSSProperties,
  type KeyboardEvent,
  type RefObject,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { Icon } from "../icon/icon";
import styles from "./searchable-select.module.css";

export type SearchableSelectOption = {
  label: string;
  value: string;
};

type PopupPosition = {
  bottom: number | null;
  left: number;
  maxHeight: number;
  top: number | null;
  width: number;
};

type SearchableSelectProps = {
  "aria-describedby"?: string | undefined;
  "aria-invalid"?: AriaAttributes["aria-invalid"];
  disabled?: boolean | undefined;
  emptyMessage?: string | undefined;
  id: string;
  inputRef?: RefObject<HTMLInputElement | null> | undefined;
  onChange: (value: string) => void;
  options: SearchableSelectOption[];
  placeholder: string;
  value: string;
};

export function SearchableSelect({
  "aria-describedby": ariaDescribedBy,
  "aria-invalid": ariaInvalid,
  disabled = false,
  emptyMessage = "Ничего не найдено",
  id,
  inputRef,
  onChange,
  options,
  placeholder,
  value,
}: SearchableSelectProps) {
  const generatedId = useId();
  const listboxId = `${id}-options-${generatedId.replaceAll(":", "")}`;
  const controlRef = useRef<HTMLDivElement>(null);
  const selectedOption = options.find((option) => option.value === value);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [popupPosition, setPopupPosition] = useState<PopupPosition | null>(
    null,
  );
  const filteredOptions = useMemo(() => {
    const normalizedQuery = normalizeSearchValue(query);
    if (!normalizedQuery) return options;
    return options.filter((option) =>
      normalizeSearchValue(option.label).includes(normalizedQuery),
    );
  }, [options, query]);
  const inputValue = open ? query : (selectedOption?.label ?? "");

  useEffect(() => {
    if (!open) return;

    function updatePopupPosition() {
      const control = controlRef.current;
      if (!control) return;
      const rect = control.getBoundingClientRect();
      const viewportPadding = 12;
      const popupGap = 4;
      const availableBelow =
        window.innerHeight - rect.bottom - viewportPadding - popupGap;
      const availableAbove = rect.top - viewportPadding - popupGap;
      const opensAbove =
        availableBelow < 160 && availableAbove > availableBelow;
      const width = Math.min(
        rect.width,
        window.innerWidth - 2 * viewportPadding,
      );
      const left = Math.min(
        Math.max(rect.left, viewportPadding),
        window.innerWidth - width - viewportPadding,
      );

      setPopupPosition({
        bottom: opensAbove ? window.innerHeight - rect.top + popupGap : null,
        left,
        maxHeight: Math.min(
          240,
          Math.max(opensAbove ? availableAbove : availableBelow, 96),
        ),
        top: opensAbove ? null : rect.bottom + popupGap,
        width,
      });
    }

    updatePopupPosition();
    window.addEventListener("resize", updatePopupPosition);
    window.addEventListener("scroll", updatePopupPosition, true);
    return () => {
      window.removeEventListener("resize", updatePopupPosition);
      window.removeEventListener("scroll", updatePopupPosition, true);
    };
  }, [open]);

  function openList() {
    if (disabled || open) return;
    setQuery("");
    setActiveIndex(
      Math.max(
        0,
        options.findIndex((option) => option.value === value),
      ),
    );
    setOpen(true);
  }

  function closeList() {
    setQuery("");
    setOpen(false);
    setPopupPosition(null);
  }

  function selectOption(option: SearchableSelectOption) {
    onChange(option.value);
    closeList();
    window.requestAnimationFrame(() => inputRef?.current?.focus());
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        openList();
        return;
      }
      const direction = event.key === "ArrowDown" ? 1 : -1;
      setActiveIndex((current) =>
        Math.min(
          Math.max(current + direction, 0),
          Math.max(filteredOptions.length - 1, 0),
        ),
      );
      return;
    }
    if (event.key === "Enter" && open) {
      event.preventDefault();
      const activeOption = filteredOptions[activeIndex];
      if (activeOption) selectOption(activeOption);
      return;
    }
    if (event.key === "Escape" && open) {
      event.preventDefault();
      closeList();
    }
  }

  return (
    <div
      className={styles.root}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          closeList();
        }
      }}
    >
      <div className={styles.control} ref={controlRef}>
        <Icon className={styles.searchIcon} name="search" size={18} />
        <input
          aria-activedescendant={
            open && filteredOptions[activeIndex]
              ? `${listboxId}-${activeIndex}`
              : undefined
          }
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-describedby={ariaDescribedBy}
          aria-expanded={open}
          aria-invalid={ariaInvalid}
          autoComplete="off"
          disabled={disabled}
          id={id}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(0);
            if (!open) setOpen(true);
          }}
          onClick={openList}
          onFocus={openList}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          ref={inputRef}
          role="combobox"
          value={inputValue}
        />
        <Icon className={styles.caret} name="expand" size={16} />
      </div>
      {open && popupPosition
        ? createPortal(
            <div className={styles.popup} style={popupStyle(popupPosition)}>
              {filteredOptions.length > 0 ? (
                <ul id={listboxId} role="listbox">
                  {filteredOptions.map((option, index) => (
                    <li
                      aria-selected={option.value === value}
                      className={
                        index === activeIndex ? styles.activeOption : ""
                      }
                      id={`${listboxId}-${index}`}
                      key={option.value}
                      onMouseDown={(event) => event.preventDefault()}
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => selectOption(option)}
                      role="option"
                    >
                      <span>{option.label}</span>
                      {option.value === value ? (
                        <Icon name="check" size={16} weight="bold" />
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className={styles.empty}>{emptyMessage}</p>
              )}
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}

function popupStyle(position: PopupPosition): CSSProperties {
  return {
    bottom: position.bottom ?? undefined,
    left: position.left,
    maxHeight: position.maxHeight,
    top: position.top ?? undefined,
    width: position.width,
  };
}

function normalizeSearchValue(value: string): string {
  return value.trim().toLocaleLowerCase("ru-RU");
}
