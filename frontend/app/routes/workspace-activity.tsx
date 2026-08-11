import { useNavigation } from "react-router";

import type { WorkspaceActivityLoadResult } from "../features/workspaces/api/workspace-activity-api";
import { WorkspaceActivityPage } from "../features/workspaces/workspace-activity-page";
import { loginHref } from "../session/unauthenticated";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/workspace-activity";
import { loadWorkspaceActivityRoute } from "./workspace-activity-loader";

export function meta() {
  return [{ title: "История действий — Booker Tee" }];
}

export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  return loadWorkspaceActivityRoute(request, params.workspaceId);
}

export default function WorkspaceActivityRoute({
  loaderData,
}: Route.ComponentProps) {
  const navigation = useNavigation();
  return (
    <WorkspaceActivityRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
    />
  );
}

export function WorkspaceActivityRouteView({
  loaderData,
  navigationPending = false,
}: {
  loaderData: Awaited<ReturnType<typeof loadWorkspaceActivityRoute>>;
  navigationPending?: boolean;
}) {
  const { activity, scope, session, workspaceId } = loaderData;
  if (
    session.status === "unauthenticated" ||
    activity.status === "unauthenticated"
  ) {
    return (
      <WorkspaceActivityRouteState
        result={{ status: "unauthenticated" }}
        scope={scope}
        workspaceId={workspaceId}
      />
    );
  }
  if (session.status === "error") {
    return (
      <WorkspaceActivityRouteState
        result={session}
        scope={scope}
        workspaceId={workspaceId}
      />
    );
  }
  if (activity.status !== "success") {
    return (
      <WorkspaceActivityRouteState
        result={activity}
        scope={scope}
        workspaceId={workspaceId}
      />
    );
  }
  if (session.status !== "authenticated") {
    return (
      <WorkspaceActivityRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
        scope={scope}
        workspaceId={workspaceId}
      />
    );
  }
  return (
    <WorkspaceActivityPage
      initialActivity={activity.activity}
      navigationPending={navigationPending}
      scope={scope}
      session={session.session}
    />
  );
}

function WorkspaceActivityRouteState({
  result,
  scope,
  workspaceId,
}: {
  result: Exclude<WorkspaceActivityLoadResult, { status: "success" }>;
  scope: string;
  workspaceId: string;
}) {
  const unauthenticated = result.status === "unauthenticated";
  const notFound = result.status === "not_found";
  const forbidden = result.status === "forbidden";
  const retryable = result.status === "error";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated
          ? loginHref("/app/workspaces")
          : retryable
            ? `/app/workspaces/${workspaceId}/activity?scope=${scope}`
            : "/app/workspaces"
      }
      actionIcon={unauthenticated ? "forward" : retryable ? "retry" : "back"}
      actionLabel={
        unauthenticated
          ? "Войти"
          : retryable
            ? "Повторить"
            : "Рабочие пространства"
      }
      eyebrow={
        unauthenticated
          ? "Сессия не найдена"
          : notFound
            ? "Пространство не найдено"
            : result.status === "forbidden"
              ? "Недостаточно прав"
              : "Ошибка загрузки"
      }
      kind={
        unauthenticated
          ? "unauthenticated"
          : notFound
            ? "notFound"
            : forbidden
              ? "forbidden"
              : "error"
      }
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : notFound
            ? "Такого пространства нет"
            : result.status === "forbidden"
              ? "История действий недоступна"
              : "Не удалось загрузить историю"
      }
    >
      {!unauthenticated && !notFound ? result.message : null}
    </RouteStatePage>
  );
}
