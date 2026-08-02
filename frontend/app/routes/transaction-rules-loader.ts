import { loadSession } from "../api/session";
import { loadTransactionRules } from "../features/transaction-rules/api/transaction-rules-api";
import { transactionRuleApiSearch } from "../features/transaction-rules/transaction-rule-list-query";

export async function loadTransactionRulesRoute(request: Request) {
  const search = transactionRuleApiSearch(new URL(request.url).search);
  const [session, rules] = await Promise.all([
    loadSession(request.signal),
    loadTransactionRules(search, request.signal),
  ]);
  return { rules, session };
}
