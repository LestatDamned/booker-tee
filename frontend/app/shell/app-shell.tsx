import type { ReactNode } from "react";
import { NavLink } from "react-router";

import type { SessionDto } from "../api/session";
import styles from "../styles/shell.module.css";

type AppShellProps = {
  children: ReactNode;
  session: SessionDto;
};

export function AppShell({ children, session }: AppShellProps) {
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
        </nav>
      </aside>
      <main className={styles.workspace}>
        <header className={styles.workspaceHeader}>
          <div>
            <p className={styles.eyebrow}>Текущий workspace</p>
            <p className={styles.workspaceName}>{session.workspace.name}</p>
          </div>
          <div className={styles.userChip}>
            <span>{session.user.name ?? session.user.email}</span>
            <small>{session.membership.role}</small>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

function navClassName({ isActive }: { isActive: boolean }) {
  return `${styles.navItem} ${isActive ? styles.navItemActive : ""}`;
}
