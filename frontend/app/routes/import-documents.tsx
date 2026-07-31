import { useNavigation } from "react-router";

import type { ImportDocumentListLoadResult } from "../features/import-documents/api/import-documents-api";
import { ImportDocumentListPage } from "../features/import-documents/import-document-list-page";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/import-documents";
import { loadImportDocumentsRoute } from "./import-documents-loader";

export { loadImportDocumentsRoute } from "./import-documents-loader";

export function meta() {
  return [{ title: "Импорты — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadImportDocumentsRoute(request);
}

export default function ImportDocumentsRoute({
  loaderData,
}: Route.ComponentProps) {
  const navigation = useNavigation();
  return (
    <ImportDocumentsRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
    />
  );
}

export function ImportDocumentsRouteView({
  loaderData,
  navigationPending = false,
}: {
  loaderData: Awaited<ReturnType<typeof loadImportDocumentsRoute>>;
  navigationPending?: boolean;
}) {
  const { documents, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    documents.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") {
    return <RouteState result={session} />;
  }
  if (documents.status === "error") {
    return <RouteState result={documents} />;
  }
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <ImportDocumentListPage
      documents={documents.documents}
      navigationPending={navigationPending}
      session={session.session}
    />
  );
}

function RouteState({
  result,
}: {
  result: Exclude<ImportDocumentListLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated ? "/login?next=/app/imports" : window.location.href
      }
      actionLabel={unauthenticated ? "Войти" : "Повторить"}
      eyebrow={unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      kind={unauthenticated ? "unauthenticated" : "error"}
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : "Не удалось загрузить документы"
      }
    >
      {!unauthenticated ? result.message : null}
    </RouteStatePage>
  );
}
