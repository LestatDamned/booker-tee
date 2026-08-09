import { loadSession } from "../api/session";
import { loadAccounts } from "../features/accounts/api/accounts-api";
import { loadCategories } from "../features/categories/api/categories-api";
import { loadDebtDetail } from "../features/debts/api/debts-api";

export async function loadDebtDetailRoute(request: Request, debtId: string) {
  const url = new URL(request.url);
  const page = positiveInteger(url.searchParams.get("page"), 1);
  const pageSize = Math.min(
    100,
    positiveInteger(url.searchParams.get("page_size"), 20),
  );
  const [session, detail, accounts, categories] = await Promise.all([
    loadSession(request.signal),
    loadDebtDetail(debtId, page, pageSize, request.signal),
    loadAccounts(request.signal),
    loadCategories(request.signal),
  ]);
  return { accounts, categories, detail, session };
}

function positiveInteger(value: string | null, fallback: number): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}
