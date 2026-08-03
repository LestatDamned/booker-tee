import { useNavigation } from "react-router";

import { ReportsPage } from "../features/reports/reports-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
import type { Route } from "./+types/reports";
import { loadReportsRoute } from "./reports-loader";

export { loadReportsRoute } from "./reports-loader";

export function meta() {
  return [{ title: "Отчёты — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadReportsRoute(request);
}

export default function ReportsRoute({ loaderData }: Route.ComponentProps) {
  const navigation = useNavigation();
  return (
    <ReportsRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
    />
  );
}

export function ReportsRouteView({
  loaderData,
  navigationPending = false,
}: {
  loaderData: Awaited<ReturnType<typeof loadReportsRoute>>;
  navigationPending?: boolean;
}) {
  const { reports, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    reports.status === "unauthenticated"
  ) {
    return <ReportsRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <ReportsRouteState result={session} />;
  if (reports.status === "error") return <ReportsRouteState result={reports} />;
  if (session.status !== "authenticated") {
    return (
      <ReportsRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <ReportsPage
      navigationPending={navigationPending}
      overview={reports.overview}
      session={session.session}
    />
  );
}

function ReportsRouteState({ result }: { result: AuthenticatedRouteFailure }) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить отчёт"
      result={result}
      returnTo="/app/reports"
    />
  );
}
