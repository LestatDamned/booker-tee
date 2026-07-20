import type { SessionLoadResult } from "../api/session";

export function SessionShell({ result }: { result: SessionLoadResult }) {
  if (result.status === "loading") {
    return (
      <main className="centered-state" aria-busy="true">
        <p className="eyebrow">Booker Tee</p>
        <h1>Загружаем workspace…</h1>
      </main>
    );
  }

  if (result.status === "unauthenticated") {
    return (
      <main className="centered-state">
        <p className="eyebrow">Сессия не найдена</p>
        <h1>Войдите в Booker Tee</h1>
        <p>После входа вы вернётесь в новый frontend.</p>
        <a className="button-link" href="/login?next=/app">
          Войти
        </a>
      </main>
    );
  }

  if (result.status === "error") {
    return (
      <main className="centered-state" role="alert">
        <p className="eyebrow">Ошибка соединения</p>
        <h1>Не удалось загрузить workspace</h1>
        <p>{result.message}</p>
        <button
          className="button-link"
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
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/app">
          Booker Tee
        </a>
        <nav aria-label="Главная навигация">
          <span className="nav-item nav-item--active">Обзор</span>
          <span className="nav-item">Операции — скоро</span>
        </nav>
      </aside>
      <main className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Текущий workspace</p>
            <h1>{session.workspace.name}</h1>
          </div>
          <div className="user-chip">
            <span>{session.user.name ?? session.user.email}</span>
            <small>{session.membership.role}</small>
          </div>
        </header>
        <section className="placeholder-card">
          <p className="eyebrow">Stage 01</p>
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
