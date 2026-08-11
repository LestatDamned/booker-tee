import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { SessionDto } from "../../api/session";
import type { DashboardOverviewDto } from "./api/dashboard-api";
import { DashboardPage, documentHref } from "./dashboard-page";
import { dashboardPayload } from "./test-support";

describe("DashboardPage", () => {
  it("shows compact attention and the last full month without mixing currencies", () => {
    renderPage(dashboardPayload);

    expect(
      screen.getByRole("heading", { name: "Требует внимания" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Финансовый итог" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/июль 2026.*полный месяц/)).toBeInTheDocument();
    expect(screen.getByLabelText(/\+125.*000,00 RUB/)).toBeInTheDocument();
    expect(screen.getByLabelText(/−65.*000,00 RUB/)).toBeInTheDocument();
    expect(screen.getByLabelText(/9.*118,88 RUB/)).toBeInTheDocument();
    expect(screen.getByLabelText(/2.*300,00 USD/)).toBeInTheDocument();
    expect(screen.getByText(/без внутренних переводов/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /август 2026.*на сегодня/ }),
    ).toHaveAttribute(
      "href",
      "/reports?date_from=2026-08-01&date_to=2026-08-05",
    );
  });

  it("uses the server-selected primary action and document next step", () => {
    renderPage(dashboardPayload);

    const uploadActions = screen.getAllByRole("link", {
      name: "Загрузить выписку",
    });
    expect(
      uploadActions.find((link) => link.dataset.tone === "primary"),
    ).toHaveAttribute("href", "/imports/upload");
    expect(screen.getByRole("link", { name: "Проверить" })).toHaveAttribute(
      "href",
      "/imports/documents/d56b94b3-eb88-4db2-9b89-db5b7dce683f/review",
    );
    expect(screen.queryByText("Следующий шаг")).not.toBeInTheDocument();
    expect(screen.getByText("july-statement.pdf")).toBeInTheDocument();
    expect(screen.getByText(/выписка по 31\.07\.2026/)).toBeInTheDocument();
  });

  it("shows a calm healthy state and hides completed onboarding", () => {
    renderPage({
      ...dashboardPayload,
      attention: { total: 0, items: [] },
      onboarding: {
        hasAccounts: true,
        hasDocuments: true,
        hasConfirmedActivity: true,
        isComplete: true,
      },
    });

    expect(
      screen.getByText("Нет открытых импортов на проверке"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Следующий шаг")).not.toBeInTheDocument();
  });

  it("shows only the next onboarding action", () => {
    renderPage({
      ...dashboardPayload,
      accounts: [],
      activeAccountCount: 0,
      attention: { total: 0, items: [] },
      onboarding: {
        hasAccounts: false,
        hasDocuments: false,
        hasConfirmedActivity: false,
        isComplete: false,
      },
      recentDocuments: [],
    });

    expect(screen.getByText("Следующий шаг")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Добавьте первый счёт" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Загрузите первую выписку"),
    ).not.toBeInTheDocument();
  });

  it("opens the last full month when reports are the primary action", () => {
    renderPage({
      ...dashboardPayload,
      capabilities: {
        canUpload: false,
        canWriteFinancialData: false,
        primaryAction: "reports",
      },
    });

    const primary = screen
      .getAllByRole("link", { name: "Открыть отчёт" })
      .find((link) => link.dataset.tone === "primary");
    expect(primary).toHaveAttribute(
      "href",
      "/reports?date_from=2026-07-01&date_to=2026-07-31",
    );
  });

  it("uses the canonical operations route for manual entry", () => {
    renderPage({
      ...dashboardPayload,
      capabilities: {
        ...dashboardPayload.capabilities,
        primaryAction: "manual_operation",
      },
      onboarding: {
        hasAccounts: true,
        hasDocuments: true,
        hasConfirmedActivity: false,
        isComplete: false,
      },
      recentDocuments: [],
    });

    expect(
      screen
        .getAllByRole("link", { name: /Добавить операцию|Продолжить/ })
        .every((link) => link.getAttribute("href") === "/operations"),
    ).toBe(true);
  });

  it("builds only canonical React document routes", () => {
    const document = dashboardPayload.attention.items[0]!;
    expect(documentHref(document)).toBe(
      "/imports/documents/d56b94b3-eb88-4db2-9b89-db5b7dce683f/review",
    );
    expect(documentHref({ ...document, nextStepKind: "mapping" })).toContain(
      "/mapping",
    );
    expect(documentHref({ ...document, nextStepKind: "detail" })).toBe(
      "/imports/documents/d56b94b3-eb88-4db2-9b89-db5b7dce683f",
    );
  });
});

function renderPage(dashboard: DashboardOverviewDto) {
  return render(
    <MemoryRouter>
      <DashboardPage dashboard={dashboard} session={session} />
    </MemoryRouter>,
  );
}

const session: SessionDto = {
  user: {
    id: "2290fe02-81cb-477e-a0e1-589783f8b316",
    email: "max@example.test",
    name: "Max",
  },
  workspace: {
    id: "53a112fc-8907-4692-8bf6-35128684b535",
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
