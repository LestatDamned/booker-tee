import { loadSession } from "../api/session";
import { loadAccountDetail } from "../features/accounts/api/account-detail-api";

export async function loadAccountDetailRoute(
  request: Request,
  accountId: string,
) {
  const url = new URL(request.url);
  const apiSearch = accountDetailApiSearch(url.search);
  const [session, detail] = await Promise.all([
    loadSession(request.signal),
    loadAccountDetail(accountId, apiSearch, request.signal),
  ]);
  return { detail, session };
}

export function accountDetailApiSearch(currentSearch: string): string {
  const search = new URLSearchParams(currentSearch);
  search.delete("return_to");
  const value = search.toString();
  return value ? `?${value}` : "";
}
