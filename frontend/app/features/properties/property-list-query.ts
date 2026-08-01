import type { PropertySummaryDto } from "./api/properties-api";

export type PropertyListView = "active" | "archived";

export function propertyListQuery(search: string): {
  search: string;
  view: PropertyListView;
} {
  const params = new URLSearchParams(search);
  return {
    search: normalizeSearch(params.get("search") ?? ""),
    view: params.get("view") === "archived" ? "archived" : "active",
  };
}

export function propertyListUrl(view: PropertyListView, search: string) {
  const params = new URLSearchParams();
  if (view === "archived") params.set("view", "archived");
  const normalizedSearch = normalizeSearch(search);
  if (normalizedSearch) params.set("search", normalizedSearch);
  const query = params.toString();
  return query ? `?${query}` : ".";
}

export function propertyMatchesSearch(
  property: PropertySummaryDto,
  search: string,
) {
  if (!search) return true;
  const normalized = search.toLocaleLowerCase("ru-RU");
  return [property.name, property.shortName, property.address].some((value) =>
    value?.toLocaleLowerCase("ru-RU").includes(normalized),
  );
}

function normalizeSearch(search: string) {
  return search.trim().replace(/\s+/g, " ");
}
