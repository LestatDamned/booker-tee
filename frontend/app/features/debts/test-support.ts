import type { SessionDto } from "../../api/session";
import type { AccountSummaryDto } from "../accounts/api/accounts-api";
import type { CategorySummaryDto } from "../categories/api/categories-api";
import type { DebtDetailDto, DebtPortfolioDto } from "./api/debts-api";

export const session: SessionDto = {
  capabilities: {
    canManageImports: true,
    canViewRawImportData: true,
    canViewMemberDirectory: true,
    canManageMembers: true,
    canViewWorkspaceActivity: true,
    canManageWorkspace: true,
    canReadWorkspace: true,
    canWriteFinancialData: true,
  },
  csrfToken: "csrf-token",
  membership: { role: "owner", status: "active" },
  user: {
    email: "max@example.test",
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    name: "Max",
  },
  workspace: {
    defaultCurrency: "RUB",
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    name: "Дом",
    type: "personal",
  },
};

export const account: AccountSummaryDto = {
  accountType: "card",
  balance: "100000.00",
  balanceDirection: "positive",
  capabilities: { canArchive: true, canRestore: false },
  currency: "RUB",
  id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  initialBalance: "100000.00",
  isActive: true,
  movementCount: 1,
  name: "Основная карта",
  updatedAt: "2026-08-09T12:00:00Z",
};

export const expenseCategory: CategorySummaryDto = {
  activeRuleCount: 0,
  capabilities: {
    archiveBlockedReasonCode: null,
    canArchive: true,
    canDelete: false,
    canRestore: false,
    canUpdate: true,
  },
  deleteBlockers: {
    childCategoryCount: 0,
    operationCount: 1,
    rawSuggestionCount: 0,
    reasonCodes: ["active_category", "operations"],
    ruleCount: 0,
  },
  id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  isActive: true,
  isSystem: false,
  kind: "expense",
  name: "Проценты по кредитам",
  notes: null,
  operationCount: 1,
  ruleCount: 0,
  systemKey: null,
  updatedAt: "2026-08-09T12:00:00Z",
};

export const debt = {
  accountId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
  availableCredit: null,
  balance: "-75000.00",
  capabilities: {
    canArchive: false,
    canDelete: false,
    canRecordPayment: true,
    canRestore: false,
    canUpdate: true,
    deleteBlockedReason: "financial_history" as const,
    paymentBlockedReason: null,
  },
  creditLimit: null,
  currency: "RUB",
  isActive: true,
  kind: "loan_payable" as const,
  maturityDate: "2028-12-31",
  name: "Кредит на ремонт",
  openedOn: "2026-01-10",
  originalPrincipal: "100000.00",
  outstanding: "75000.00",
  status: "active" as const,
  updatedAt: "2026-08-09T12:00:00Z",
};

export const payment = {
  canUndo: true,
  createdAt: "2026-08-09T12:00:00Z",
  interest: {
    amount: "1000.00",
    description: "Платёж за август",
    operationDate: "2026-08-09",
    operationId: "ffffffff-ffff-4fff-8fff-ffffffffffff",
    operationType: "expense" as const,
    status: "confirmed" as const,
    version: 1,
  },
  notes: null,
  paymentId: "12121212-1212-4212-8212-121212121212",
  principal: {
    amount: "5000.00",
    description: "Платёж за август",
    operationDate: "2026-08-09",
    operationId: "13131313-1313-4313-8313-131313131313",
    operationType: "transfer" as const,
    status: "confirmed" as const,
    version: 1,
  },
  reversedAt: null,
};

export const detail: DebtDetailDto = {
  debt,
  notes: "Без графика платежей",
  paymentTotals: { interest: "1000.00", principal: "5000.00" },
  payments: {
    hasNext: false,
    hasPrevious: false,
    items: [payment],
    page: 1,
    pageSize: 20,
    total: 1,
    totalPages: 1,
  },
};

export const portfolio: DebtPortfolioDto = {
  capabilities: { canCreate: true, readonlyReasonCode: null },
  items: [debt],
  totals: [
    {
      currency: "RUB",
      netPosition: "-75000.00",
      payable: "75000.00",
      receivable: "0.00",
    },
    {
      currency: "USD",
      netPosition: "500.00",
      payable: "0.00",
      receivable: "500.00",
    },
  ],
};
