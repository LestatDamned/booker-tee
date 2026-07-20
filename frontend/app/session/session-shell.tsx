import type { SessionLoadResult } from "../api/session";
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
    <div className={styles.appShell}>
      <aside className={styles.sidebar}>
        <a className={styles.brand} href="/app">
          Booker Tee
        </a>
        <nav aria-label="Главная навигация">
          <span className={`${styles.navItem} ${styles.navItemActive}`}>
            Обзор
          </span>
          <span className={styles.navItem}>Операции — скоро</span>
        </nav>
      </aside>
      <main className={styles.workspace}>
        <header className={styles.workspaceHeader}>
          <div>
            <p className={styles.eyebrow}>Текущий workspace</p>
            <h1>{session.workspace.name}</h1>
          </div>
          <div className={styles.userChip}>
            <span>{session.user.name ?? session.user.email}</span>
            <small>{session.membership.role}</small>
          </div>
        </header>
        <section className={styles.placeholderCard}>
          <p className={styles.eyebrow}>Stage 01</p>
          <h2>React-контур подключён</h2>
          <p>
            Сессия и права загружены через versioned JSON API. Финансовые данные
            здесь пока не показываются.
          </p>
        </section>
      </main>
    </div>
  );
}
