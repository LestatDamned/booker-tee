import { loadSession } from "../api/session";
import { loadAccounts } from "../features/accounts/api/accounts-api";
import { loadDebts } from "../features/debts/api/debts-api";

export async function loadDebtsRoute(request: Request) {
  const [session, debts, accounts] = await Promise.all([
    loadSession(request.signal),
    loadDebts(request.signal),
    loadAccounts(request.signal),
  ]);
  return { accounts, debts, session };
}
