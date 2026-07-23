import { useRef, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router";

import type { SessionDto } from "../api/session";
import styles from "../styles/shell.module.css";

type AppShellProps = {
  children: ReactNode;
  session: SessionDto;
};

type NavIconName =
  | "accounts"
  | "categories"
  | "home"
  | "imports"
  | "operations"
  | "properties"
  | "reports"
  | "rules";

type NavigationItem = {
  href: string;
  icon: NavIconName;
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
      { href: "/accounts", icon: "accounts", label: "Счета" },
      {
        href: "/ledger/manual",
        icon: "operations",
        label: "Ручные операции",
        reactRoute: true,
      },
      { href: "/imports", icon: "imports", label: "Импорты" },
    ],
  },
  {
    label: "Анализ",
    items: [{ href: "/reports", icon: "reports", label: "Отчёты" }],
  },
  {
    label: "Справочники",
    items: [
      { href: "/categories", icon: "categories", label: "Категории" },
      { href: "/properties", icon: "properties", label: "Объекты" },
      { href: "/rules", icon: "rules", label: "Правила" },
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
            <MenuIcon />
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

      <main className={styles.workspace}>{children}</main>
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
          →
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
      <NavIcon name={item.icon} />
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

const navIconPaths: Record<NavIconName, string> = {
  accounts: "M3 7h18v12H3zM3 10h18M7 15h4",
  categories: "M4 5h9l7 7-8 8-8-8V5zM8 9h.01",
  home: "M3 11.5 12 4l9 7.5V20h-6v-5H9v5H3z",
  imports: "M12 3v12M7 10l5 5 5-5M4 20h16",
  operations: "M4 7h16M7 4 4 7l3 3M20 17H4m13-3 3 3-3 3",
  properties: "M4 20V8l8-5 8 5v12M9 20v-5h6v5M8 10h.01M12 10h.01M16 10h.01",
  reports: "M4 20V10h4v10M10 20V4h4v16M16 20v-7h4v7M3 20h18",
  rules: "M4 7h10M18 7h2M4 17h2M10 17h10M14 4v6M6 14v6",
};

function NavIcon({ name }: { name: NavIconName }) {
  return (
    <svg aria-hidden="true" className={styles.navIcon} viewBox="0 0 24 24">
      <path d={navIconPaths[name]} />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg aria-hidden="true" className={styles.menuIcon} viewBox="0 0 24 24">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}
