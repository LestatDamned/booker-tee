import type { ReactNode } from "react";

import { FormError } from "./form-error";
import styles from "./fieldset.module.css";

type FieldsetProps = {
  children: ReactNode;
  error?: string;
  errorId?: string;
  hint?: string;
  legend: string;
  required?: boolean;
};

export function Fieldset({
  children,
  error,
  errorId,
  hint,
  legend,
  required = false,
}: FieldsetProps) {
  return (
    <fieldset
      aria-describedby={error && errorId ? errorId : undefined}
      className={styles.fieldset}
    >
      <legend className={styles.legend}>
        {legend}
        {required ? <span aria-hidden="true"> *</span> : null}
      </legend>
      {hint && !error ? <p className={styles.hint}>{hint}</p> : null}
      {error ? (
        errorId ? (
          <FormError id={errorId}>{error}</FormError>
        ) : (
          <FormError>{error}</FormError>
        )
      ) : null}
      {children}
    </fieldset>
  );
}
