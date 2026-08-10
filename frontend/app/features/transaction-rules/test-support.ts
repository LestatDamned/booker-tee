import type { SessionDto } from "../../api/session";
import type { TransactionRuleDirectoryDto } from "./api/transaction-rules-api";

export const ruleId = "2ef5a75b-a1d8-4d78-8942-c859989de6c2";
export const categoryId = "af249add-4f5b-46a3-a125-654d402ccbd9";

export const session: SessionDto = {
  user: {
    id: "f4835818-f111-41d6-a59d-62f541ace357",
    email: "max@example.test",
    name: "Max",
  },
  workspace: {
    id: "c12c9ac8-6851-4467-b87a-da7fc70586c8",
    name: "Дом",
    type: "personal",
    defaultCurrency: "RUB",
  },
  membership: { role: "owner", status: "active" },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canViewRawImportData: true,
    canViewMemberDirectory: true,
    canManageMembers: true,
    canViewWorkspaceActivity: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};

export const directory: TransactionRuleDirectoryDto = {
  items: [
    {
      id: ruleId,
      name: "OZON → Маркетплейсы",
      priority: 20,
      isActive: true,
      updatedAt: "2026-08-02T09:00:00Z",
      condition: {
        pattern: "OZON",
        matchType: "contains",
        direction: "outflow",
        account: {
          id: "d5a7d84d-8091-4c74-b1ad-9b5349fd30da",
          name: "Карта",
          isActive: true,
        },
        amountMin: "100.00",
        amountMax: "500.00",
      },
      outcome: {
        operationType: "expense",
        category: { id: categoryId, name: "Маркетплейсы", isActive: true },
        property: {
          id: "b6120b55-cbab-45b1-b643-8289fe8726f9",
          name: "Старая квартира",
          isActive: false,
        },
        applicationMode: "suggest",
        autoDescription: "Покупка на маркетплейсе",
        affectsProfit: true,
      },
      usage: { directRawSuggestionCount: 4 },
      capabilities: {
        canUpdate: true,
        canEnable: false,
        canDisable: true,
        canDelete: false,
        enableBlockedReasonCode: null,
        deleteBlockedReasonCode: "active_rule",
      },
    },
  ],
  page: {
    page: 1,
    pageSize: 50,
    total: 1,
    totalPages: 1,
    hasPrevious: false,
    hasNext: false,
  },
  counts: { all: 3, active: 2, disabled: 1 },
  appliedFilters: { q: null, categoryId: null, status: "all" },
  references: {
    categories: [
      { id: categoryId, name: "Маркетплейсы", isActive: true },
      {
        id: "f8123582-352f-408e-8c91-e69e0a8ecda9",
        name: "Архивная категория",
        isActive: false,
      },
    ],
    properties: [
      {
        id: "b6120b55-cbab-45b1-b643-8289fe8726f9",
        name: "Старая квартира",
        isActive: false,
      },
    ],
  },
  capabilities: {
    canCreate: true,
    canSeedDefaults: true,
    readonlyReasonCode: null,
  },
  targetItem: null,
};
