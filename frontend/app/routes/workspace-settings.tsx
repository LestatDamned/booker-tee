import { useNavigation } from "react-router";

import type { WorkspaceSettingsLoadResult } from "../features/workspaces/api/workspace-settings-api";
import { WorkspaceSettingsPage } from "../features/workspaces/workspace-settings-page";
import { loginHref } from "../session/unauthenticated";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/workspace-settings";
import { loadWorkspaceSettingsRoute } from "./workspace-settings-loader";

export function meta() {
  return [{ title: "Настройки пространства — Booker Tee" }];
}

export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  return loadWorkspaceSettingsRoute(request, params.workspaceId);
}

export default function WorkspaceSettingsRoute({
  loaderData,
}: Route.ComponentProps) {
  const navigation = useNavigation();
  return (
    <WorkspaceSettingsRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
    />
  );
}

export function WorkspaceSettingsRouteView({
  loaderData,
  navigationPending = false,
}: {
  loaderData: Awaited<ReturnType<typeof loadWorkspaceSettingsRoute>>;
  navigationPending?: boolean;
}) {
  const { session, settings } = loaderData;
  if (
    session.status === "unauthenticated" ||
    settings.status === "unauthenticated"
  ) {
    return (
      <WorkspaceSettingsRouteState result={{ status: "unauthenticated" }} />
    );
  }
  if (session.status === "error") {
    return <WorkspaceSettingsRouteState result={session} />;
  }
  if (settings.status !== "success") {
    return <WorkspaceSettingsRouteState result={settings} />;
  }
  if (session.status !== "authenticated") {
    return (
      <WorkspaceSettingsRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <WorkspaceSettingsPage
      initialSettings={settings.settings}
      navigationPending={navigationPending}
      session={session.session}
    />
  );
}

function WorkspaceSettingsRouteState({
  result,
}: {
  result: Exclude<WorkspaceSettingsLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  const notFound = result.status === "not_found";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated ? loginHref("/app/workspaces") : "/app/workspaces"
      }
      actionIcon={unauthenticated ? "forward" : "back"}
      actionLabel={unauthenticated ? "Войти" : "Рабочие пространства"}
      eyebrow={
        unauthenticated
          ? "Сессия не найдена"
          : notFound
            ? "Пространство не найдено"
            : "Ошибка загрузки"
      }
      kind={
        unauthenticated ? "unauthenticated" : notFound ? "notFound" : "error"
      }
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : notFound
            ? "Такого пространства нет"
            : "Не удалось загрузить настройки"
      }
    >
      {!unauthenticated && !notFound ? result.message : null}
    </RouteStatePage>
  );
}
