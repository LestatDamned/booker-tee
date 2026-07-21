import { loadSession } from "../api/session";
import { loadManualLedger } from "../features/manual-ledger/api/manual-ledger-api";

export async function loadManualLedgerRoute(request: Request) {
  const search = manualLedgerApiSearch(new URL(request.url).search);
  const [session, ledger] = await Promise.all([
    loadSession(),
    loadManualLedger(search),
  ]);
  return { session, ledger };
}

export function manualLedgerApiSearch(currentSearch: string): string {
  const search = new URLSearchParams(currentSearch);
  search.delete("layout");
  return search.size > 0 ? `?${search.toString()}` : "";
}
