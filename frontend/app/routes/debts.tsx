import { DebtListPage } from "../features/debts/debt-list-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
import type { Route } from "./+types/debts";
import { loadDebtsRoute } from "./debts-loader";

export function meta() {
  return [{ title: "Долги — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadDebtsRoute(request);
}

export default function DebtsRoute({ loaderData }: Route.ComponentProps) {
  const { accounts, debts, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    debts.status === "unauthenticated" ||
    accounts.status === "unauthenticated"
  ) {
    return <DebtsRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <DebtsRouteState result={session} />;
  if (debts.status === "error") return <DebtsRouteState result={debts} />;
  if (accounts.status === "error") return <DebtsRouteState result={accounts} />;
  if (session.status !== "authenticated") {
    return (
      <DebtsRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <DebtListPage
      accounts={accounts.directory.items}
      portfolio={debts.portfolio}
      session={session.session}
    />
  );
}

function DebtsRouteState({ result }: { result: AuthenticatedRouteFailure }) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить долги"
      result={result}
      returnTo="/app/debts"
    />
  );
}
