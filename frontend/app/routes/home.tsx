import { DashboardPage } from "../features/dashboard/dashboard-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
import type { Route } from "./+types/home";
import { loadDashboardRoute } from "./dashboard-loader";

export { loadDashboardRoute } from "./dashboard-loader";

export function meta() {
  return [
    { title: "Booker Tee" },
    { name: "description", content: "Financial workbench" },
  ];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadDashboardRoute(request);
}

export default function Home({ loaderData }: Route.ComponentProps) {
  return <DashboardRouteView loaderData={loaderData} />;
}

export function DashboardRouteView({
  loaderData,
}: {
  loaderData: Awaited<ReturnType<typeof loadDashboardRoute>>;
}) {
  const { dashboard, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    dashboard.status === "unauthenticated"
  ) {
    return <DashboardRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error")
    return <DashboardRouteState result={session} />;
  if (dashboard.status === "error")
    return <DashboardRouteState result={dashboard} />;
  if (session.status !== "authenticated") {
    return (
      <DashboardRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <DashboardPage dashboard={dashboard.dashboard} session={session.session} />
  );
}

function DashboardRouteState({
  result,
}: {
  result: AuthenticatedRouteFailure;
}) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить обзор"
      result={result}
      returnTo="/app"
    />
  );
}
