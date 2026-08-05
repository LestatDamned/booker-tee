import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { SessionDto } from "../../api/session";
import type { DashboardOverviewDto } from "./api/dashboard-api";
import { DashboardPage, documentHref } from "./dashboard-page";
import { dashboardPayload } from "./test-support";

describe("DashboardPage", () => {
  it("puts attention before truthful monthly money and keeps currencies separate", () => {
    renderPage(dashboardPayload);

    expect(
      screen.getByRole("heading", { name: "Требует внимания" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Результат месяца" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/\+125.*000,00 RUB/)).toBeInTheDocument();
    expect(screen.getByLabelText(/−65.*000,00 RUB/)).toBeInTheDocument();
    expect(screen.getByLabelText(/9.*118,88 RUB/)).toBeInTheDocument();
    expect(screen.getByLabelText(/2.*300,00 USD/)).toBeInTheDocument();
    expect(
      screen.getByText(/Внутренние переводы не входят/),
    ).toBeInTheDocument();
  });

  it("uses the server-selected primary action and document next step", () => {
    renderPage(dashboardPayload);

    const uploadActions = screen.getAllByRole("link", {
      name: "Загрузить выписку",
    });
    expect(
      uploadActions.find((link) => link.dataset.tone === "primary"),
    ).toHaveAttribute("href", "/imports/upload");
    expect(screen.getByRole("link", { name: /statement.pdf/ })).toHaveAttribute(
      "href",
      "/imports/documents/d56b94b3-eb88-4db2-9b89-db5b7dce683f/review",
    );
    expect(
      screen.getByRole("heading", { name: "Первые шаги" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Сейчас")).toBeInTheDocument();
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
      screen.getByText("Нет данных, требующих решения"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Первые шаги" }),
    ).not.toBeInTheDocument();
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
    canManageMembers: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};
