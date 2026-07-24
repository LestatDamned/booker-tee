import type { ImportDocumentDetailLoadResult } from "../features/import-document-detail/api/import-document-detail-api";
import { ImportDocumentDetailPage } from "../features/import-document-detail/import-document-detail-page";
import styles from "../styles/shell.module.css";
import type { Route } from "./+types/import-document-detail";
import { loadImportDocumentDetailRoute } from "./import-document-detail-loader";

export function meta() {
  return [{ title: "Выписка — Booker Tee" }];
}

export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  return loadImportDocumentDetailRoute(params.documentId, request.signal);
}

export default function ImportDocumentDetailRoute({
  loaderData,
}: Route.ComponentProps) {
  return <ImportDocumentDetailRouteView loaderData={loaderData} />;
}

export function ImportDocumentDetailRouteView({
  loaderData,
}: {
  loaderData: Awaited<ReturnType<typeof loadImportDocumentDetailRoute>>;
}) {
  const { document, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    document.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <RouteState result={session} />;
  if (document.status !== "success") return <RouteState result={document} />;
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <ImportDocumentDetailPage
      initialDocument={document.document}
      session={session.session}
    />
  );
}

function RouteState({
  result,
}: {
  result: Exclude<ImportDocumentDetailLoadResult, { status: "success" }>;
}) {
  const copy = routeStateCopy(result);
  return (
    <main
      className={styles.centeredState}
      role={result.status === "unauthenticated" ? undefined : "alert"}
    >
      <p className={styles.eyebrow}>Документ импорта</p>
      <h1>{copy.title}</h1>
      <p>{copy.message}</p>
      <a className={styles.buttonLink} href={copy.href}>
        {copy.action}
      </a>
    </main>
  );
}

function routeStateCopy(
  result: Exclude<ImportDocumentDetailLoadResult, { status: "success" }>,
) {
  if (result.status === "unauthenticated") {
    return {
      title: "Войдите в Booker Tee",
      message: "Для просмотра выписки нужна активная сессия.",
      action: "Войти",
      href: `/login?next=${encodeURIComponent(window.location.pathname)}`,
    };
  }
  if (result.status === "forbidden") {
    return {
      title: "Нет доступа к workspace",
      message: "Ваша роль не позволяет открыть этот документ.",
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
    title: "Не удалось загрузить выписку",
    message: result.message,
    action: "Повторить",
    href: window.location.href,
  };
}
