import { ImportUploadPage } from "../features/import-upload/import-upload-page";
import styles from "../styles/shell.module.css";
import type { Route } from "./+types/import-upload";
import { loadImportUploadRoute } from "./import-upload-loader";

export { loadImportUploadRoute } from "./import-upload-loader";

export function meta() {
  return [{ title: "Загрузить выписку — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadImportUploadRoute(request);
}

export default function ImportUploadRoute({
  loaderData,
}: Route.ComponentProps) {
  const { reference, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    reference.status === "unauthenticated"
  ) {
    return <RouteState kind="unauthenticated" />;
  }
  if (session.status === "error") {
    return <RouteState kind="error" message={session.message} />;
  }
  if (reference.status === "error") {
    return <RouteState kind="error" message={reference.message} />;
  }
  if (reference.status === "forbidden") {
    return <RouteState kind="forbidden" />;
  }
  if (session.status !== "authenticated") {
    return <RouteState kind="error" message="Сессия не загружена." />;
  }
  return (
    <ImportUploadPage
      reference={reference.reference}
      session={session.session}
    />
  );
}

function RouteState({
  kind,
  message,
}: {
  kind: "unauthenticated" | "forbidden" | "error";
  message?: string;
}) {
  const title =
    kind === "unauthenticated"
      ? "Войдите в Booker Tee"
      : kind === "forbidden"
        ? "Загрузка недоступна"
        : "Не удалось открыть загрузку";
  const href =
    kind === "unauthenticated"
      ? "/login?next=/app/imports/upload"
      : "/app/imports/upload";
  return (
    <main
      className={styles.centeredState}
      role={kind === "error" ? "alert" : undefined}
    >
      <p className={styles.eyebrow}>Импорт выписки</p>
      <h1>{title}</h1>
      {message ? <p>{message}</p> : null}
      <a className={styles.buttonLink} href={href}>
        {kind === "unauthenticated" ? "Войти" : "Повторить"}
      </a>
    </main>
  );
}
