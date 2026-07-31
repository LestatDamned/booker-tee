import styles from "./request-state.module.css";

type RequestStateProps = {
  message?: string;
};

export function RequestState({
  message = "Выполняем запрос…",
}: RequestStateProps) {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={styles.state}
      role="status"
    >
      <span aria-hidden="true" className={styles.spinner} />
      <span>{message}</span>
    </div>
  );
}
