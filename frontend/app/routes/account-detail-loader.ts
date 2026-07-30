import { loadSession } from "../api/session";
import { loadAccountDetail } from "../features/accounts/api/account-detail-api";

export async function loadAccountDetailRoute(
  request: Request,
  accountId: string,
) {
  const url = new URL(request.url);
  const [session, detail] = await Promise.all([
    loadSession(request.signal),
    loadAccountDetail(accountId, url.search, request.signal),
  ]);
  return { detail, session };
}
