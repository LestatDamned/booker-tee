import type { ImportMappingLoadResult } from "../features/import-mapping/api/import-mapping-api";
import { ImportMappingPage } from "../features/import-mapping/import-mapping-page";
import styles from "../styles/shell.module.css";
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
    <main
      className={styles.centeredState}
      role={result.status === "unauthenticated" ? undefined : "alert"}
    >
      <p className={styles.eyebrow}>Настройка импорта</p>
      <h1>{copy.title}</h1>
      <p>{copy.message}</p>
      <a className={styles.buttonLink} href={copy.href}>
        {copy.action}
      </a>
    </main>
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
      href: `/login?next=${encodeURIComponent(window.location.pathname)}`,
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
