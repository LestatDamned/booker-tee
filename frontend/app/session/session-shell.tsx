import type { SessionLoadResult } from "../api/session";
import { AppShell } from "../shell/app-shell";
import styles from "../styles/shell.module.css";

export function SessionShell({ result }: { result: SessionLoadResult }) {
  if (result.status === "loading") {
    return (
      <main className={styles.centeredState} aria-busy="true">
        <p className={styles.eyebrow}>Booker Tee</p>
        <h1>Загружаем workspace…</h1>
      </main>
    );
  }

  if (result.status === "unauthenticated") {
    return (
      <main className={styles.centeredState}>
        <p className={styles.eyebrow}>Сессия не найдена</p>
        <h1>Войдите в Booker Tee</h1>
        <p>После входа вы вернётесь в новый frontend.</p>
        <a className={styles.buttonLink} href="/login?next=/app">
          Войти
        </a>
      </main>
    );
  }

  if (result.status === "error") {
    return (
      <main className={styles.centeredState} role="alert">
        <p className={styles.eyebrow}>Ошибка соединения</p>
        <h1>Не удалось загрузить workspace</h1>
        <p>{result.message}</p>
        <button
          className={styles.buttonLink}
          type="button"
          onClick={() => window.location.reload()}
        >
          Повторить
        </button>
      </main>
    );
  }

  const { session } = result;
  return (
    <AppShell session={session}>
      <section className={styles.placeholderCard}>
        <p className={styles.eyebrow}>React frontend</p>
        <h1>Рабочий контур подключён</h1>
        <p>
          Первый финансовый read workflow доступен в разделе ручных операций.
        </p>
      </section>
    </AppShell>
  );
}
