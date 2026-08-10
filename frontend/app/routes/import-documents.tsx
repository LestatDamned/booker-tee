import { useNavigation } from "react-router";

import { ImportDocumentListPage } from "../features/import-documents/import-document-list-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
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
    return <ImportDocumentsRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") {
    return <ImportDocumentsRouteState result={session} />;
  }
  if (documents.status === "error") {
    return <ImportDocumentsRouteState result={documents} />;
  }
  if (documents.status === "forbidden") {
    return <ImportDocumentsRouteState result={documents} />;
  }
  if (session.status !== "authenticated") {
    return (
      <ImportDocumentsRouteState
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

function ImportDocumentsRouteState({
  result,
}: {
  result: AuthenticatedRouteFailure;
}) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить документы"
      {...(result.status === "error"
        ? { retryHref: window.location.href }
        : {})}
      result={result}
      returnTo="/app/imports"
    />
  );
}
