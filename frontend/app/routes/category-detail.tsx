import { useNavigation } from "react-router";

import type { CategoryDetailLoadResult } from "../features/categories/api/category-detail-api";
import { CategoryDetailPage } from "../features/categories/category-detail-page";
import { loginHref } from "../session/unauthenticated";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/category-detail";
import { loadCategoryDetailRoute } from "./category-detail-loader";

export function meta() {
  return [{ title: "Категория — Booker Tee" }];
}

export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  return loadCategoryDetailRoute(request, params.categoryId);
}

export default function CategoryDetailRoute({
  loaderData,
}: Route.ComponentProps) {
  const navigation = useNavigation();
  return (
    <CategoryDetailRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
    />
  );
}

export function CategoryDetailRouteView({
  loaderData,
  navigationPending = false,
}: {
  loaderData: Awaited<ReturnType<typeof loadCategoryDetailRoute>>;
  navigationPending?: boolean;
}) {
  const { detail, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    detail.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <RouteState result={session} />;
  if (detail.status !== "success") return <RouteState result={detail} />;
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <CategoryDetailPage
      detail={detail.detail}
      navigationPending={navigationPending}
      session={session.session}
    />
  );
}

function RouteState({
  result,
}: {
  result: Exclude<CategoryDetailLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  const notFound = result.status === "not_found";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated ? loginHref("/app/categories") : "/app/categories"
      }
      actionIcon={unauthenticated ? "forward" : "back"}
      actionLabel={unauthenticated ? "Войти" : "Все категории"}
      eyebrow={
        unauthenticated
          ? "Сессия не найдена"
          : notFound
            ? "Категория не найдена"
            : "Ошибка загрузки"
      }
      kind={
        unauthenticated ? "unauthenticated" : notFound ? "notFound" : "error"
      }
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : notFound
            ? "Такой категории нет"
            : "Не удалось загрузить категорию"
      }
    >
      {!unauthenticated && !notFound ? result.message : null}
    </RouteStatePage>
  );
}
