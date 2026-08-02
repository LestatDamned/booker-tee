import { useNavigation } from "react-router";

import type { TransactionRuleDirectoryLoadResult } from "../features/transaction-rules/api/transaction-rules-api";
import { TransactionRulesPage } from "../features/transaction-rules/transaction-rules-page";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
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
  return (
    <TransactionRulesRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
    />
  );
}

export function TransactionRulesRouteView({
  loaderData,
  navigationPending = false,
}: {
  loaderData: Awaited<ReturnType<typeof loadTransactionRulesRoute>>;
  navigationPending?: boolean;
}) {
  const { rules, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    rules.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <RouteState result={session} />;
  if (rules.status === "error") return <RouteState result={rules} />;
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <TransactionRulesPage
      directory={rules.directory}
      navigationPending={navigationPending}
      session={session.session}
    />
  );
}

function RouteState({
  result,
}: {
  result: Exclude<TransactionRuleDirectoryLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated ? "/login?next=/app/rules" : window.location.href
      }
      actionLabel={unauthenticated ? "Войти" : "Повторить"}
      eyebrow={unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      kind={unauthenticated ? "unauthenticated" : "error"}
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : "Не удалось загрузить правила операций"
      }
    >
      {!unauthenticated ? result.message : null}
    </RouteStatePage>
  );
}
