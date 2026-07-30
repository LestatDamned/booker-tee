import type { AccountDirectoryLoadResult } from "../features/accounts/api/accounts-api";
import { AccountListPage } from "../features/accounts/account-list-page";
import styles from "../styles/shell.module.css";
import type { Route } from "./+types/accounts";
import { loadAccountsRoute } from "./accounts-loader";

export { loadAccountsRoute } from "./accounts-loader";

export function meta() {
  return [{ title: "Счета — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadAccountsRoute(request);
}

export default function AccountsRoute({ loaderData }: Route.ComponentProps) {
  return <AccountsRouteView loaderData={loaderData} />;
}

export function AccountsRouteView({
  loaderData,
}: {
  loaderData: Awaited<ReturnType<typeof loadAccountsRoute>>;
}) {
  const { accounts, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    accounts.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") {
    return <RouteState result={session} />;
  }
  if (accounts.status === "error") {
    return <RouteState result={accounts} />;
  }
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <AccountListPage directory={accounts.directory} session={session.session} />
  );
}

function RouteState({
  result,
}: {
  result: Exclude<AccountDirectoryLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  return (
    <main
      className={styles.centeredState}
      role={unauthenticated ? undefined : "alert"}
    >
      <p className={styles.eyebrow}>
        {unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      </p>
      <h1>
        {unauthenticated
          ? "Войдите в Booker Tee"
          : "Не удалось загрузить счета"}
      </h1>
      {!unauthenticated ? <p>{result.message}</p> : null}
      <a
        className={styles.buttonLink}
        href={unauthenticated ? "/login?next=/app/accounts" : "/app/accounts"}
      >
        {unauthenticated ? "Войти" : "Повторить"}
      </a>
    </main>
  );
}
