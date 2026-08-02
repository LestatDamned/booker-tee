import type { ReactNode } from "react";

import { FormError } from "./form-error";
import styles from "./field.module.css";

type FieldProps = {
  children: ReactNode;
  error?: string | undefined;
  errorId?: string;
  hint?: string;
  hintId?: string;
  htmlFor: string;
  label: ReactNode;
  required?: boolean;
};

export function Field({
  children,
  error,
  errorId,
  hint,
  hintId,
  htmlFor,
  label,
  required = false,
}: FieldProps) {
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={htmlFor}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {children}
      {hint && !error ? (
        <span className={styles.hint} id={hintId ?? `${htmlFor}-hint`}>
          {hint}
        </span>
      ) : null}
      {error ? (
        errorId ? (
          <FormError id={errorId}>{error}</FormError>
        ) : (
          <FormError>{error}</FormError>
        )
      ) : null}
    </div>
  );
}
