import { loadSession } from "../api/session";
import { loadCategoryDetail } from "../features/categories/api/category-detail-api";
import { categoryDetailApiSearch } from "../features/categories/category-detail-query";

export async function loadCategoryDetailRoute(
  request: Request,
  categoryId: string,
) {
  const url = new URL(request.url);
  const [session, detail] = await Promise.all([
    loadSession(request.signal),
    loadCategoryDetail(
      categoryId,
      categoryDetailApiSearch(url.search),
      request.signal,
    ),
  ]);
  return { detail, session };
}
