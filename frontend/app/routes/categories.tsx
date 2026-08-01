import type { CategoryDirectoryLoadResult } from "../features/categories/api/categories-api";
import { CategoriesPage } from "../features/categories/categories-page";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/categories";
import { loadCategoriesRoute } from "./categories-loader";

export { loadCategoriesRoute } from "./categories-loader";

export function meta() {
  return [{ title: "Категории — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadCategoriesRoute(request);
}

export default function CategoriesRoute({ loaderData }: Route.ComponentProps) {
  return <CategoriesRouteView loaderData={loaderData} />;
}

export function CategoriesRouteView({
  loaderData,
}: {
  loaderData: Awaited<ReturnType<typeof loadCategoriesRoute>>;
}) {
  const { categories, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    categories.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <RouteState result={session} />;
  if (categories.status === "error") return <RouteState result={categories} />;
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <CategoriesPage
      directory={categories.directory}
      session={session.session}
    />
  );
}

function RouteState({
  result,
}: {
  result: Exclude<CategoryDirectoryLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated ? "/login?next=/app/categories" : "/app/categories"
      }
      actionLabel={unauthenticated ? "Войти" : "Повторить"}
      eyebrow={unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      kind={unauthenticated ? "unauthenticated" : "error"}
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : "Не удалось загрузить категории"
      }
    >
      {!unauthenticated ? result.message : null}
    </RouteStatePage>
  );
}
