import { useNavigation } from "react-router";

import type { AccountDetailLoadResult } from "../features/accounts/api/account-detail-api";
import { AccountDetailPage } from "../features/accounts/account-detail-page";
import { loginHref } from "../session/unauthenticated";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/account-detail";
import { loadAccountDetailRoute } from "./account-detail-loader";

export function meta() {
  return [{ title: "Счёт — Booker Tee" }];
}

export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  return loadAccountDetailRoute(request, params.accountId);
}

export default function AccountDetailRoute({
  loaderData,
}: Route.ComponentProps) {
  const navigation = useNavigation();
  return (
    <AccountDetailRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
    />
  );
}

export function AccountDetailRouteView({
  loaderData,
  navigationPending = false,
}: {
  loaderData: Awaited<ReturnType<typeof loadAccountDetailRoute>>;
  navigationPending?: boolean;
}) {
  const { detail, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    detail.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <RouteState result={session} />;
  if (detail.status !== "success") return <RouteState result={detail} />;
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <AccountDetailPage
      detail={detail.detail}
      navigationPending={navigationPending}
      session={session.session}
    />
  );
}

function RouteState({
  result,
}: {
  result: Exclude<AccountDetailLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  const notFound = result.status === "not_found";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated ? loginHref("/app/accounts") : "/app/accounts"
      }
      actionIcon={unauthenticated ? "forward" : "back"}
      actionLabel={unauthenticated ? "Войти" : "К списку счетов"}
      eyebrow={
        unauthenticated
          ? "Сессия не найдена"
          : notFound
            ? "Счёт не найден"
            : "Ошибка загрузки"
      }
      kind={
        unauthenticated ? "unauthenticated" : notFound ? "notFound" : "error"
      }
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : notFound
            ? "Такого счёта нет в workspace"
            : "Не удалось загрузить проводки"
      }
    >
      {result.status === "error" ? result.message : null}
    </RouteStatePage>
  );
}
