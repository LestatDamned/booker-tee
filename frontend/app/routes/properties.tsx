import { PropertiesPage } from "../features/properties/properties-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
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
    return <PropertiesRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error")
    return <PropertiesRouteState result={session} />;
  if (properties.status === "error")
    return <PropertiesRouteState result={properties} />;
  if (session.status !== "authenticated") {
    return (
      <PropertiesRouteState
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

function PropertiesRouteState({
  result,
}: {
  result: AuthenticatedRouteFailure;
}) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить объекты"
      result={result}
      returnTo="/app/properties"
    />
  );
}
