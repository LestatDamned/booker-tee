import { loadSession } from "../api/session";
import { loadAccounts } from "../features/accounts/api/accounts-api";

export async function loadAccountsRoute(request: Request) {
  const [session, accounts] = await Promise.all([
    loadSession(request.signal),
    loadAccounts(request.signal),
  ]);
  return { accounts, session };
}
