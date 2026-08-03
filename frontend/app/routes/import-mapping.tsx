import type { ImportMappingLoadResult } from "../features/import-mapping/api/import-mapping-api";
import { ImportMappingPage } from "../features/import-mapping/import-mapping-page";
import { loginHref } from "../session/unauthenticated";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/import-mapping";
import { loadImportMappingRoute } from "./import-mapping-loader";

export function meta() {
  return [{ title: "Настройка импорта — Booker Tee" }];
}

export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  return loadImportMappingRoute(params.documentId, request.signal);
}

export default function ImportMappingRoute({
  loaderData,
}: Route.ComponentProps) {
  return <ImportMappingRouteView loaderData={loaderData} />;
}

export function ImportMappingRouteView({
  loaderData,
}: {
  loaderData: Awaited<ReturnType<typeof loadImportMappingRoute>>;
}) {
  const { mapping, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    mapping.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <RouteState result={session} />;
  if (mapping.status !== "success") return <RouteState result={mapping} />;
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <ImportMappingPage mapping={mapping.mapping} session={session.session} />
  );
}

function RouteState({
  result,
}: {
  result: Exclude<ImportMappingLoadResult, { status: "success" }>;
}) {
  const copy = routeStateCopy(result);
  return (
    <RouteStatePage
      actionHref={copy.href}
      actionLabel={copy.action}
      eyebrow="Настройка импорта"
      kind={
        result.status === "unauthenticated"
          ? "unauthenticated"
          : result.status === "forbidden"
            ? "forbidden"
            : result.status === "not_found"
              ? "notFound"
              : "error"
      }
      title={copy.title}
    >
      {copy.message}
    </RouteStatePage>
  );
}

function routeStateCopy(
  result: Exclude<ImportMappingLoadResult, { status: "success" }>,
) {
  if (result.status === "unauthenticated") {
    return {
      title: "Войдите в Booker Tee",
      message: "Для настройки выписки нужна активная сессия.",
      action: "Войти",
      href: loginHref(window.location.pathname),
    };
  }
  if (result.status === "forbidden") {
    return {
      title: "Нет доступа к workspace",
      message: "Ваша роль не позволяет настраивать этот документ.",
      action: "На главную",
      href: "/app",
    };
  }
  if (result.status === "not_found") {
    return {
      title: "Документ не найден",
      message: "Документ удалён или относится к другому workspace.",
      action: "К импортам",
      href: "/app/imports",
    };
  }
  return {
    title: "Не удалось загрузить настройку",
    message: result.message,
    action: "Повторить",
    href: window.location.href,
  };
}
