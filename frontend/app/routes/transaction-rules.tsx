import { useNavigation, useRevalidator } from "react-router";

import { TransactionRulesPage } from "../features/transaction-rules/transaction-rules-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
import type { Route } from "./+types/transaction-rules";
import { loadTransactionRulesRoute } from "./transaction-rules-loader";

export { loadTransactionRulesRoute } from "./transaction-rules-loader";

export function meta() {
  return [{ title: "Правила операций — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadTransactionRulesRoute(request);
}

export default function TransactionRulesRoute({
  loaderData,
}: Route.ComponentProps) {
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  return (
    <TransactionRulesRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
      onReload={() => void revalidator.revalidate()}
    />
  );
}

export function TransactionRulesRouteView({
  loaderData,
  navigationPending = false,
  onReload,
}: {
  loaderData: Awaited<ReturnType<typeof loadTransactionRulesRoute>>;
  navigationPending?: boolean;
  onReload?: () => void;
}) {
  const { rules, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    rules.status === "unauthenticated"
  ) {
    return (
      <TransactionRulesRouteState result={{ status: "unauthenticated" }} />
    );
  }
  if (session.status === "error")
    return <TransactionRulesRouteState result={session} />;
  if (rules.status === "error")
    return <TransactionRulesRouteState result={rules} />;
  if (session.status !== "authenticated") {
    return (
      <TransactionRulesRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <TransactionRulesPage
      directory={rules.directory}
      navigationPending={navigationPending}
      {...(onReload ? { onReload } : {})}
      session={session.session}
    />
  );
}

function TransactionRulesRouteState({
  result,
}: {
  result: AuthenticatedRouteFailure;
}) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить правила операций"
      {...(result.status === "error"
        ? { retryHref: window.location.href }
        : {})}
      result={result}
      returnTo="/app/rules"
    />
  );
}
