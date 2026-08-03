import { AccountListPage } from "../features/accounts/account-list-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
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
    return <AccountsRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") {
    return <AccountsRouteState result={session} />;
  }
  if (accounts.status === "error") {
    return <AccountsRouteState result={accounts} />;
  }
  if (session.status !== "authenticated") {
    return (
      <AccountsRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <AccountListPage directory={accounts.directory} session={session.session} />
  );
}

function AccountsRouteState({ result }: { result: AuthenticatedRouteFailure }) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить счета"
      result={result}
      returnTo="/app/accounts"
    />
  );
}
