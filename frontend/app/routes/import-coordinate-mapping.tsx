import { VisualCoordinateMappingPage } from "../features/import-coordinate-mapping/page";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import { loginHref } from "../session/unauthenticated";
import { useLocation } from "react-router";
import type { Route } from "./+types/import-coordinate-mapping";
import { loadImportCoordinateMappingRoute } from "./import-coordinate-mapping-loader";

export function meta() {
  return [{ title: "Визуальная настройка PDF — Booker Tee" }];
}
export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  return loadImportCoordinateMappingRoute(params.documentId, request.signal);
}
export default function ImportCoordinateMappingRoute({
  loaderData,
}: Route.ComponentProps) {
  const location = useLocation();
  const { overview, session } = loaderData;
  if (session.status === "authenticated" && overview.status === "success")
    return (
      <VisualCoordinateMappingPage
        overview={overview.value}
        session={session.session}
      />
    );
  const unauthenticated =
    session.status === "unauthenticated" ||
    overview.status === "unauthenticated";
  const notFound = overview.status === "not_found";
  const forbidden = overview.status === "forbidden";
  const message =
    "message" in overview
      ? overview.message
      : session.status === "error"
        ? session.message
        : "Страница недоступна.";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated
          ? loginHref(`${location.pathname}${location.search}${location.hash}`)
          : "/app/imports"
      }
      actionLabel={unauthenticated ? "Войти" : "К импортам"}
      eyebrow="Визуальная настройка PDF"
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
            ? "Документ не найден"
            : forbidden
              ? "Нет доступа"
              : "Не удалось загрузить настройку"
      }
    >
      {message}
    </RouteStatePage>
  );
}
