import { useNavigation } from "react-router";

import type { DebtDetailLoadResult } from "../features/debts/api/debts-api";
import { DebtDetailPage } from "../features/debts/debt-detail-page";
import { loginHref } from "../session/unauthenticated";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/debt-detail";
import { loadDebtDetailRoute } from "./debt-detail-loader";

export function meta() {
  return [{ title: "Долг — Booker Tee" }];
}

export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  return loadDebtDetailRoute(request, params.debtId);
}

export default function DebtDetailRoute({ loaderData }: Route.ComponentProps) {
  const navigation = useNavigation();
  const { accounts, categories, detail, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    detail.status === "unauthenticated" ||
    accounts.status === "unauthenticated" ||
    categories.status === "unauthenticated"
  ) {
    return <DebtRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <DebtRouteState result={session} />;
  if (detail.status !== "success") return <DebtRouteState result={detail} />;
  if (accounts.status === "error") return <DebtRouteState result={accounts} />;
  if (categories.status === "error")
    return <DebtRouteState result={categories} />;
  if (session.status !== "authenticated") {
    return (
      <DebtRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <DebtDetailPage
      accounts={accounts.directory.items}
      categories={categories.directory.items}
      detail={detail.detail}
      navigationPending={navigation.state !== "idle"}
      session={session.session}
    />
  );
}

function DebtRouteState({
  result,
}: {
  result: Exclude<DebtDetailLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  const notFound = result.status === "not_found";
  return (
    <RouteStatePage
      actionHref={unauthenticated ? loginHref("/app/debts") : "/app/debts"}
      actionIcon={unauthenticated ? "forward" : "back"}
      actionLabel={unauthenticated ? "Войти" : "Все долги"}
      eyebrow={
        unauthenticated
          ? "Сессия не найдена"
          : notFound
            ? "Долг не найден"
            : "Ошибка загрузки"
      }
      kind={
        unauthenticated ? "unauthenticated" : notFound ? "notFound" : "error"
      }
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : notFound
            ? "Такого долга нет"
            : "Не удалось загрузить долг"
      }
    >
      {!unauthenticated && !notFound ? result.message : null}
    </RouteStatePage>
  );
}
