import { loadSession } from "../api/session";
import { loadCategories } from "../features/categories/api/categories-api";

export async function loadCategoriesRoute(request: Request) {
  const [session, categories] = await Promise.all([
    loadSession(request.signal),
    loadCategories(request.signal),
  ]);
  return { categories, session };
}
