import type { ImportReviewLoadResult } from "../features/import-review/api/import-review-api";
import { ImportReviewPage } from "../features/import-review/import-review-page";
import styles from "../styles/shell.module.css";
import type { Route } from "./+types/import-review";
import { loadImportReviewRoute } from "./import-review-loader";

export function meta() {
  return [{ title: "Проверка импорта — Booker Tee" }];
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  return loadImportReviewRoute(params.documentId);
}

export default function ImportReviewRoute({
  loaderData,
}: Route.ComponentProps) {
  return <ImportReviewRouteView loaderData={loaderData} />;
}

export function ImportReviewRouteView({
  loaderData,
}: {
  loaderData: Awaited<ReturnType<typeof loadImportReviewRoute>>;
}) {
  const { review, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    review.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") {
    return <RouteState result={session} />;
  }
  if (review.status !== "success") {
    return <RouteState result={review} />;
  }
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return <ImportReviewPage review={review.review} session={session.session} />;
}

function RouteState({
  result,
}: {
  result: Exclude<ImportReviewLoadResult, { status: "success" }>;
}) {
  const state = routeStateContent(result);
  return (
    <main
      className={styles.centeredState}
      role={result.status === "unauthenticated" ? undefined : "alert"}
    >
      <p className={styles.eyebrow}>Проверка импорта</p>
      <h1>{state.title}</h1>
      <p>{state.message}</p>
      <a className={styles.buttonLink} href={state.href}>
        {state.action}
      </a>
    </main>
  );
}

function routeStateContent(
  result: Exclude<ImportReviewLoadResult, { status: "success" }>,
) {
  if (result.status === "unauthenticated") {
    return {
      title: "Войдите в Booker Tee",
      message: "Для проверки импорта нужна активная сессия.",
      action: "Войти",
      href: `/login?next=${encodeURIComponent(window.location.pathname)}`,
    };
  }
  if (result.status === "forbidden") {
    return {
      title: "Нет доступа к workspace",
      message: "Ваша роль не позволяет открыть этот импорт.",
      action: "На главную",
      href: "/app",
    };
  }
  if (result.status === "not-found") {
    return {
      title: "Документ не найден",
      message: "Документ удалён или относится к другому workspace.",
      action: "К импортам",
      href: "/imports",
    };
  }
  return {
    title: "Не удалось загрузить проверку",
    message: result.message,
    action: "Повторить",
    href: window.location.href,
  };
}
