import type { CategoryKind, CategorySummaryDto } from "./api/categories-api";

export type CategoryListView = "active" | "archived" | "system";

export function categoryListQuery(search: string): {
  search: string;
  view: CategoryListView;
} {
  const params = new URLSearchParams(search);
  const view = params.get("view");
  return {
    search: normalizeSearch(params.get("search") ?? ""),
    view: view === "archived" || view === "system" ? view : "active",
  };
}

export function categoryListUrl(view: CategoryListView, search: string) {
  const params = new URLSearchParams();
  if (view !== "active") params.set("view", view);
  const normalizedSearch = normalizeSearch(search);
  if (normalizedSearch) params.set("search", normalizedSearch);
  const query = params.toString();
  return query ? `?${query}` : ".";
}

export function categoryMatchesView(
  category: CategorySummaryDto,
  view: CategoryListView,
) {
  if (view === "system") return category.isSystem;
  return (
    !category.isSystem &&
    (view === "active" ? category.isActive : !category.isActive)
  );
}

export function categoryMatchesSearch(
  category: CategorySummaryDto,
  search: string,
  kindLabels: ReadonlyMap<CategoryKind, string>,
) {
  if (!search) return true;
  const normalized = search.toLocaleLowerCase("ru-RU");
  return [category.name, category.notes, kindLabels.get(category.kind)].some(
    (value) => value?.toLocaleLowerCase("ru-RU").includes(normalized),
  );
}

function normalizeSearch(search: string) {
  return search.trim().replace(/\s+/g, " ");
}
