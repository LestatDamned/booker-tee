import type { SessionDto } from "../../api/session";
import type { ReportOverviewDto } from "./api/reports-api";

export const accountId = "4958dd80-af47-4131-8f16-16c0ca04f63c";
export const categoryId = "b8917470-c242-47aa-bfd4-e3b72a1bb657";
export const secondCategoryId = "7f771b41-c1d2-4fba-ad7e-6584bbc1d619";
export const propertyId = "28964070-ac60-4a7b-b637-574614bfd492";
export const secondPropertyId = "ad664fd9-b51c-4e2f-9bc0-c3484f2caa27";
export const documentId = "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8";

export const reportOverview: ReportOverviewDto = {
  workspaceName: "Дом",
  appliedFilters: {
    dateFrom: "2026-07-01",
    dateTo: "2026-07-31",
    currency: "RUB",
    accountId: null,
    categoryId: null,
    propertyId: null,
  },
  filterOptions: {
    accounts: [
      {
        id: accountId,
        name: "Основной",
        currency: "RUB",
        isActive: true,
      },
      {
        id: "74deba03-3dfa-4ab8-8f4d-7845e5e02ee9",
        name: "Архивный долларовый",
        currency: "USD",
        isActive: false,
      },
    ],
    categories: [{ id: categoryId, name: "Продукты", isActive: true }],
    properties: [{ id: propertyId, name: "Квартира", isActive: false }],
    currencies: ["RUB", "USD"],
  },
  summary: {
    currency: "RUB",
    income: "120000.00",
    expense: "45000.00",
    profit: "75000.00",
  },
  accountBalances: [
    {
      accountId,
      name: "Основной",
      currency: "RUB",
      balance: "185000.00",
      isActive: true,
    },
  ],
  categoryRows: [
    {
      categoryId,
      name: "Продукты",
      currency: "RUB",
      income: "0.00",
      expense: "45000.00",
      profit: "-45000.00",
      isActive: true,
    },
    {
      categoryId: secondCategoryId,
      name: "Продукты",
      currency: "RUB",
      income: "10000.00",
      expense: "5000.00",
      profit: "5000.00",
      isActive: false,
    },
  ],
  propertyRows: [
    {
      propertyId,
      name: "Квартира",
      currency: "RUB",
      income: "120000.00",
      expense: "30000.00",
      profit: "90000.00",
      isActive: true,
    },
    {
      propertyId: secondPropertyId,
      name: "Квартира",
      currency: "RUB",
      income: "0.00",
      expense: "10000.00",
      profit: "-10000.00",
      isActive: false,
    },
  ],
  balanceAsOf: "2026-07-31",
  nextReviewDocumentId: documentId,
};

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
  membership: { role: "viewer", status: "active" },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: false,
    canManageImports: false,
    canManageMembers: false,
    canManageWorkspace: false,
  },
  csrfToken: "csrf-token",
};
