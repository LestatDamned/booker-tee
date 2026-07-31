import { useNavigation } from "react-router";

import type { ReportOverviewLoadResult } from "../features/reports/api/reports-api";
import { ReportsPage } from "../features/reports/reports-page";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
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
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <RouteState result={session} />;
  if (reports.status === "error") return <RouteState result={reports} />;
  if (session.status !== "authenticated") {
    return (
      <RouteState
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

function RouteState({
  result,
}: {
  result: Exclude<ReportOverviewLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  return (
    <RouteStatePage
      actionHref={unauthenticated ? "/login?next=/app/reports" : "/app/reports"}
      actionLabel={unauthenticated ? "Войти" : "Повторить"}
      eyebrow={unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      kind={unauthenticated ? "unauthenticated" : "error"}
      title={
        unauthenticated ? "Войдите в Booker Tee" : "Не удалось загрузить отчёт"
      }
    >
      {!unauthenticated ? result.message : null}
    </RouteStatePage>
  );
}
