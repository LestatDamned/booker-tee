import type { ImportReviewLoadResult } from "../features/import-review/api/import-review-api";
import { ImportReviewPage } from "../features/import-review/import-review-page";
import { loginHref } from "../session/unauthenticated";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/import-review";
import { loadImportReviewRoute } from "./import-review-loader";

export function meta() {
  return [{ title: "Проверка импорта — Booker Tee" }];
}

export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  return loadImportReviewRoute(params.documentId, request.signal);
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
    <RouteStatePage
      actionHref={state.href}
      actionLabel={state.action}
      eyebrow="Проверка импорта"
      kind={
        result.status === "unauthenticated"
          ? "unauthenticated"
          : result.status === "forbidden"
            ? "forbidden"
            : result.status === "not-found"
              ? "notFound"
              : "error"
      }
      title={state.title}
    >
      {state.message}
    </RouteStatePage>
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
      href: loginHref(window.location.pathname),
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
      href: "/app/imports",
    };
  }
  return {
    title: "Не удалось загрузить проверку",
    message: result.message,
    action: "Повторить",
    href: window.location.href,
  };
}
