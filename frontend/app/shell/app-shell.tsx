import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router";

import type { SessionDto } from "../api/session";
import styles from "../styles/shell.module.css";

type AppShellProps = {
  children: ReactNode;
  session: SessionDto;
};

export function AppShell({ children, session }: AppShellProps) {
  const location = useLocation();
  const importsActive = location.pathname.startsWith("/imports");

  return (
    <div className={styles.appShell}>
      <aside className={styles.sidebar}>
        <NavLink className={styles.brand ?? ""} end to="/">
          Booker Tee
        </NavLink>
        <nav aria-label="Главная навигация">
          <NavLink className={navClassName} end to="/">
            Обзор
          </NavLink>
          <NavLink className={navClassName} to="/ledger/manual">
            Ручные операции
          </NavLink>
          <a
            aria-current={importsActive ? "page" : undefined}
            className={externalNavClassName(importsActive)}
            href="/imports"
          >
            Импорты
          </a>
        </nav>
      </aside>
      <header className={styles.mobileHeader}>
        <NavLink className={styles.brand ?? ""} end to="/">
          Booker Tee
        </NavLink>
        <details className={styles.mobileMenu}>
          <summary>Меню</summary>
          <nav aria-label="Мобильная навигация">
            <NavLink className={navClassName} end to="/">
              Обзор
            </NavLink>
            <NavLink className={navClassName} to="/ledger/manual">
              Ручные операции
            </NavLink>
            <a
              aria-current={importsActive ? "page" : undefined}
              className={externalNavClassName(importsActive)}
              href="/imports"
            >
              Импорты
            </a>
          </nav>
        </details>
      </header>
      <main className={styles.workspace}>
        <header className={styles.workspaceHeader}>
          <div>
            <p className={styles.eyebrow}>Текущий workspace</p>
            <p className={styles.workspaceName}>{session.workspace.name}</p>
          </div>
          <div className={styles.userChip}>
            <span>{session.user.name ?? session.user.email}</span>
            <small>{membershipRoleLabel(session.membership.role)}</small>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

function membershipRoleLabel(role: SessionDto["membership"]["role"]): string {
  const labels: Record<SessionDto["membership"]["role"], string> = {
    owner: "Владелец",
    admin: "Администратор",
    editor: "Редактор",
    viewer: "Только чтение",
    uploader: "Загрузка данных",
    analyst: "Аналитик",
  };
  return labels[role];
}

function navClassName({ isActive }: { isActive: boolean }) {
  return `${styles.navItem} ${isActive ? styles.navItemActive : ""}`;
}

function externalNavClassName(isActive: boolean) {
  return navClassName({ isActive });
}
