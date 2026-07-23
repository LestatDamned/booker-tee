import { useNavigation } from "react-router";

import type { ImportDocumentListLoadResult } from "../features/import-documents/api/import-documents-api";
import { ImportDocumentListPage } from "../features/import-documents/import-document-list-page";
import styles from "../styles/shell.module.css";
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
    <main
      className={styles.centeredState}
      role={unauthenticated ? undefined : "alert"}
    >
      <p className={styles.eyebrow}>
        {unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      </p>
      <h1>
        {unauthenticated
          ? "Войдите в Booker Tee"
          : "Не удалось загрузить документы"}
      </h1>
      {!unauthenticated ? <p>{result.message}</p> : null}
      <a
        className={styles.buttonLink}
        href={
          unauthenticated ? "/login?next=/app/imports" : window.location.href
        }
      >
        {unauthenticated ? "Войти" : "Повторить"}
      </a>
    </main>
  );
}
