import type { SessionLoadResult } from "../api/session";
import { AppShell } from "../shell/app-shell";
import styles from "../styles/shell.module.css";
import { RouteLoadingPage } from "../ui/route-state-page/route-loading-page";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import { loginHref } from "./unauthenticated";

export function SessionShell({ result }: { result: SessionLoadResult }) {
  if (result.status === "loading") {
    return (
      <RouteLoadingPage eyebrow="Booker Tee" title="Загружаем workspace…" />
    );
  }

  if (result.status === "unauthenticated") {
    return (
      <RouteStatePage
        actionHref={loginHref("/app")}
        actionLabel="Войти"
        eyebrow="Сессия не найдена"
        kind="unauthenticated"
        title="Войдите в Booker Tee"
      >
        После входа вы вернётесь в новый frontend.
      </RouteStatePage>
    );
  }

  if (result.status === "error") {
    return (
      <RouteStatePage
        actionHref="/app"
        actionLabel="Повторить"
        eyebrow="Ошибка соединения"
        kind="error"
        title="Не удалось загрузить workspace"
      >
        {result.message}
      </RouteStatePage>
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
