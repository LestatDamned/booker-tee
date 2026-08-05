import { forwardRef, useState, type ComponentPropsWithoutRef } from "react";

import styles from "./password-input.module.css";

type PasswordInputProps = Omit<ComponentPropsWithoutRef<"input">, "type">;

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  function PasswordInput(props, ref) {
    const [visible, setVisible] = useState(false);
    return (
      <div className={styles.wrapper}>
        <input {...props} ref={ref} type={visible ? "text" : "password"} />
        <button
          aria-controls={props.id}
          aria-pressed={visible}
          className={styles.toggle}
          disabled={props.disabled}
          onClick={() => setVisible((current) => !current)}
          type="button"
        >
          {visible ? "Скрыть" : "Показать"}
        </button>
      </div>
    );
  },
);
