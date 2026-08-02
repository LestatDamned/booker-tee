import { useRef, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router";

import type { SessionDto } from "../api/session";
import { Icon, type IconName } from "../ui/icon/icon";
import styles from "../styles/shell.module.css";

type AppShellProps = {
  children: ReactNode;
  session: SessionDto;
};

type NavigationItem = {
  href: string;
  icon: IconName;
  label: string;
  reactRoute?: boolean;
};

type NavigationGroup = {
  label: string;
  items: ReadonlyArray<NavigationItem>;
};

const navigationGroups: ReadonlyArray<NavigationGroup> = [
  {
    label: "Работа",
    items: [
      { href: "/", icon: "home", label: "Обзор", reactRoute: true },
      {
        href: "/accounts",
        icon: "accounts",
        label: "Счета",
        reactRoute: true,
      },
      {
        href: "/ledger/manual",
        icon: "operations",
        label: "Ручные операции",
        reactRoute: true,
      },
      {
        href: "/imports",
        icon: "imports",
        label: "Импорты",
        reactRoute: true,
      },
    ],
  },
  {
    label: "Анализ",
    items: [
      {
        href: "/reports",
        icon: "reports",
        label: "Отчёты",
        reactRoute: true,
      },
    ],
  },
  {
    label: "Справочники",
    items: [
      {
        href: "/categories",
        icon: "categories",
        label: "Категории",
        reactRoute: true,
      },
      {
        href: "/properties",
        icon: "properties",
        label: "Объекты",
        reactRoute: true,
      },
      { href: "/rules", icon: "rules", label: "Правила", reactRoute: true },
    ],
  },
];

export function AppShell({ children, session }: AppShellProps) {
  const location = useLocation();
  const mobileMenuRef = useRef<HTMLDetailsElement>(null);
  const userLabel = session.user.name ?? session.user.email;

  function closeMobileMenu() {
    if (mobileMenuRef.current) {
      mobileMenuRef.current.open = false;
    }
  }

  function closeMobileMenuAndRestoreFocus() {
    closeMobileMenu();
    mobileMenuRef.current?.querySelector("summary")?.focus();
  }

  return (
    <div className={styles.appShell}>
      <a className={styles.skipLink} href="#app-main-content">
        Перейти к содержимому
      </a>

      <aside className={styles.sidebar}>
        <NavLink className={styles.brand ?? ""} end to="/">
          Booker Tee
        </NavLink>
        <ShellContext
          currentPath={location.pathname}
          session={session}
          userLabel={userLabel}
        />
      </aside>

      <header className={styles.mobileHeader}>
        <NavLink className={styles.brand ?? ""} end to="/">
          Booker Tee
        </NavLink>
        <a
          className={styles.mobileWorkspace}
          href="/workspaces"
          title={session.workspace.name}
        >
          {session.workspace.name}
        </a>
        <details
          className={styles.mobileMenu}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              closeMobileMenuAndRestoreFocus();
            }
          }}
          ref={mobileMenuRef}
        >
          <summary>
            <Icon className={styles.menuIcon} name="menu" size={20} />
            <span>Меню</span>
          </summary>
          <div className={styles.mobileMenuPanel}>
            <ShellContext
              currentPath={location.pathname}
              onNavigate={closeMobileMenu}
              session={session}
              userLabel={userLabel}
            />
          </div>
        </details>
      </header>

      <main className={styles.workspace} id="app-main-content" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}

type ShellContextProps = {
  currentPath: string;
  onNavigate?: (() => void) | undefined;
  session: SessionDto;
  userLabel: string;
};

function ShellContext({
  currentPath,
  onNavigate,
  session,
  userLabel,
}: ShellContextProps) {
  return (
    <div className={styles.shellContext}>
      <a
        aria-label={`Текущий workspace: ${session.workspace.name}. Открыть пространства`}
        className={styles.workspaceCard}
        href="/workspaces"
        onClick={onNavigate}
      >
        <span className={styles.contextEyebrow}>Текущий workspace</span>
        <strong title={session.workspace.name}>{session.workspace.name}</strong>
        <small>Все пространства</small>
      </a>

      <ShellNavigation currentPath={currentPath} onNavigate={onNavigate} />

      <a
        className={styles.userCard}
        href="/users"
        onClick={onNavigate}
        aria-label={`${userLabel}. ${membershipRoleLabel(session.membership.role)}. Открыть профиль`}
      >
        <span aria-hidden="true" className={styles.userAvatar}>
          {userInitials(userLabel)}
        </span>
        <span className={styles.userIdentity}>
          <strong title={userLabel}>{userLabel}</strong>
          <small>{membershipRoleLabel(session.membership.role)}</small>
        </span>
        <span aria-hidden="true" className={styles.contextArrow}>
          <Icon name="forward" size={16} />
        </span>
      </a>
    </div>
  );
}

function ShellNavigation({
  currentPath,
  onNavigate,
}: {
  currentPath: string;
  onNavigate?: (() => void) | undefined;
}) {
  return (
    <nav aria-label={onNavigate ? "Мобильная навигация" : "Главная навигация"}>
      {navigationGroups.map((group) => (
        <section className={styles.navGroup} key={group.label}>
          <p className={styles.navGroupLabel}>{group.label}</p>
          <div className={styles.navList}>
            {group.items.map((item) => (
              <ShellNavigationItem
                currentPath={currentPath}
                item={item}
                key={item.href}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        </section>
      ))}
    </nav>
  );
}

function ShellNavigationItem({
  currentPath,
  item,
  onNavigate,
}: {
  currentPath: string;
  item: NavigationItem;
  onNavigate?: (() => void) | undefined;
}) {
  const content = (
    <>
      <Icon className={styles.navIcon} name={item.icon} size={20} />
      <span>{item.label}</span>
    </>
  );

  if (item.reactRoute) {
    return (
      <NavLink
        className={navClassName}
        end={item.href === "/"}
        onClick={onNavigate}
        to={item.href}
      >
        {content}
      </NavLink>
    );
  }

  const active = pathMatches(currentPath, item.href);
  return (
    <a
      aria-current={active ? "page" : undefined}
      className={externalNavClassName(active)}
      href={item.href}
      onClick={onNavigate}
    >
      {content}
    </a>
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

function userInitials(label: string): string {
  const words = label
    .trim()
    .split(/[\s@._-]+/)
    .filter(Boolean);
  const initials = words
    .slice(0, 2)
    .map((word) => Array.from(word)[0]?.toLocaleUpperCase("ru-RU") ?? "")
    .join("");
  return initials || "BT";
}

function pathMatches(currentPath: string, href: string): boolean {
  return currentPath === href || currentPath.startsWith(`${href}/`);
}

function navClassName({ isActive }: { isActive: boolean }) {
  return `${styles.navItem} ${isActive ? styles.navItemActive : ""}`;
}

function externalNavClassName(isActive: boolean) {
  return navClassName({ isActive });
}
