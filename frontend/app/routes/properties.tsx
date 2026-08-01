import type { PropertyDirectoryLoadResult } from "../features/properties/api/properties-api";
import { PropertiesPage } from "../features/properties/properties-page";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/properties";
import { loadPropertiesRoute } from "./properties-loader";

export { loadPropertiesRoute } from "./properties-loader";

export function meta() {
  return [{ title: "Объекты — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadPropertiesRoute(request);
}

export default function PropertiesRoute({ loaderData }: Route.ComponentProps) {
  return <PropertiesRouteView loaderData={loaderData} />;
}

export function PropertiesRouteView({
  loaderData,
}: {
  loaderData: Awaited<ReturnType<typeof loadPropertiesRoute>>;
}) {
  const { properties, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    properties.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <RouteState result={session} />;
  if (properties.status === "error") return <RouteState result={properties} />;
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <PropertiesPage
      directory={properties.directory}
      session={session.session}
    />
  );
}

function RouteState({
  result,
}: {
  result: Exclude<PropertyDirectoryLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated ? "/login?next=/app/properties" : "/app/properties"
      }
      actionLabel={unauthenticated ? "Войти" : "Повторить"}
      eyebrow={unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      kind={unauthenticated ? "unauthenticated" : "error"}
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : "Не удалось загрузить объекты"
      }
    >
      {!unauthenticated ? result.message : null}
    </RouteStatePage>
  );
}
