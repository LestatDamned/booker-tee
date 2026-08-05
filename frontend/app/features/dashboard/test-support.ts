import type { DashboardOverviewDto } from "./api/dashboard-api";

export const dashboardPayload: DashboardOverviewDto = {
  workspaceName: "Дом",
  period: { start: "2026-08-01", end: "2026-08-05" },
  summary: {
    currency: "RUB",
    income: "125000.00",
    expense: "65000.00",
    profit: "60000.00",
  },
  accounts: [
    {
      id: "285c18d8-78bb-46d7-b6cd-d6fc897ab8a2",
      name: "Основной",
      currency: "RUB",
      balance: "9118.88",
    },
    {
      id: "77342a59-ebd7-4583-97ad-f90c65bfcb0c",
      name: "Доллары",
      currency: "USD",
      balance: "2300.00",
    },
  ],
  activeAccountCount: 2,
  attention: {
    total: 1,
    items: [
      {
        id: "d56b94b3-eb88-4db2-9b89-db5b7dce683f",
        filename: "statement.pdf",
        status: "requires_review",
        createdAt: "2026-08-05T12:00:00Z",
        account: {
          id: "285c18d8-78bb-46d7-b6cd-d6fc897ab8a2",
          name: "Основной",
          currency: "RUB",
        },
        reviewableRowCount: 4,
        nextStepKind: "review",
      },
    ],
  },
  recentDocuments: [],
  onboarding: {
    hasAccounts: true,
    hasDocuments: true,
    hasConfirmedActivity: false,
    isComplete: false,
  },
  capabilities: {
    canUpload: true,
    canWriteFinancialData: true,
    primaryAction: "upload",
  },
};
