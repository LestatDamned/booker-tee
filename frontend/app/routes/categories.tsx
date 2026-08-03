import { CategoriesPage } from "../features/categories/categories-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
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
    return <CategoriesRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error")
    return <CategoriesRouteState result={session} />;
  if (categories.status === "error")
    return <CategoriesRouteState result={categories} />;
  if (session.status !== "authenticated") {
    return (
      <CategoriesRouteState
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

function CategoriesRouteState({
  result,
}: {
  result: AuthenticatedRouteFailure;
}) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить категории"
      result={result}
      returnTo="/app/categories"
    />
  );
}
