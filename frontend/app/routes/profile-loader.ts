import { loadSession } from "../api/session";
import { loadAccount } from "../features/users/api/account-api";

export async function loadProfileRoute(request: Request) {
  const [session, account] = await Promise.all([
    loadSession(request.signal),
    loadAccount(request.signal),
  ]);
  return { session, account };
}
