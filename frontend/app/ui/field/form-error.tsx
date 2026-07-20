import styles from "./field.module.css";

type FormErrorProps = {
  announce?: boolean;
  children: string;
  id?: string;
};

export function FormError({ announce = false, children, id }: FormErrorProps) {
  return (
    <span
      className={styles.error}
      id={id}
      role={announce ? "alert" : undefined}
    >
      {children}
    </span>
  );
}
