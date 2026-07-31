import type {
  ComponentPropsWithoutRef,
  FormEventHandler,
  ReactNode,
} from "react";

import { Button } from "../button/button";
import styles from "./workbench-toolbar.module.css";

type SearchInputProps = Omit<
  ComponentPropsWithoutRef<"input">,
  "disabled" | "id" | "name" | "placeholder" | "type"
>;

type WorkbenchSearchProps = {
  ariaLabel: string;
  className?: string | undefined;
  disabled?: boolean;
  inputId: string;
  inputLabel: string;
  inputProps?: SearchInputProps;
  name?: string;
  onSubmit: FormEventHandler<HTMLFormElement>;
  placeholder: string;
  submitLabel?: ReactNode;
};

export function WorkbenchSearch({
  ariaLabel,
  className,
  disabled = false,
  inputId,
  inputLabel,
  inputProps,
  name = "search",
  onSubmit,
  placeholder,
  submitLabel = "Найти",
}: WorkbenchSearchProps) {
  return (
    <form
      aria-label={ariaLabel}
      className={
        className === undefined
          ? styles.search
          : `${styles.search} ${className}`
      }
      onSubmit={onSubmit}
      role="search"
    >
      <label className="visually-hidden" htmlFor={inputId}>
        {inputLabel}
      </label>
      <input
        {...inputProps}
        disabled={disabled}
        id={inputId}
        name={name}
        placeholder={placeholder}
        type="search"
      />
      <Button disabled={disabled} icon="search" type="submit">
        {submitLabel}
      </Button>
    </form>
  );
}
