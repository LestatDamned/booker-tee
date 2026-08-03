import { WorkspacesPage } from "../features/workspaces/workspaces-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
import type { Route } from "./+types/workspaces";
import { loadWorkspacesRoute } from "./workspaces-loader";

export { loadWorkspacesRoute } from "./workspaces-loader";

export function meta() {
  return [{ title: "Рабочие пространства — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadWorkspacesRoute(request);
}

export default function WorkspacesRoute({ loaderData }: Route.ComponentProps) {
  return <WorkspacesRouteView loaderData={loaderData} />;
}

export function WorkspacesRouteView({
  loaderData,
}: {
  loaderData: Awaited<ReturnType<typeof loadWorkspacesRoute>>;
}) {
  const { session, workspaces } = loaderData;
  if (
    session.status === "unauthenticated" ||
    workspaces.status === "unauthenticated"
  ) {
    return <WorkspacesRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error")
    return <WorkspacesRouteState result={session} />;
  if (workspaces.status === "error") {
    return <WorkspacesRouteState result={workspaces} />;
  }
  if (session.status !== "authenticated") {
    return (
      <WorkspacesRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <WorkspacesPage
      directory={workspaces.directory}
      session={session.session}
    />
  );
}

function WorkspacesRouteState({
  result,
}: {
  result: AuthenticatedRouteFailure;
}) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить пространства"
      result={result}
      returnTo="/app/workspaces"
    />
  );
}
