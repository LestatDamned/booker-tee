import { Button } from "../button/button";
import styles from "./request-state.module.css";

type RequestStateProps =
  | { status: "loading"; message?: string }
  | { status: "empty"; message: string; title: string }
  | { status: "error"; message: string; onRetry?: () => void; title: string };

export function RequestState(props: RequestStateProps) {
  if (props.status === "loading") {
    return (
      <div aria-live="polite" className={styles.state}>
        <span aria-hidden="true" className={styles.spinner} />
        <span>{props.message ?? "Выполняем запрос…"}</span>
      </div>
    );
  }

  const isError = props.status === "error";
  return (
    <section
      className={`${styles.state} ${isError ? styles.error : styles.empty}`}
      role={isError ? "alert" : "status"}
    >
      <strong>{props.title}</strong>
      <span>{props.message}</span>
      {isError && props.onRetry ? (
        <div>
          <Button icon="retry" onClick={props.onRetry}>
            Повторить
          </Button>
        </div>
      ) : null}
    </section>
  );
}
