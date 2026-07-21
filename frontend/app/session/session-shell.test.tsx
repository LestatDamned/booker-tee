import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { SessionShell } from "./session-shell";

describe("SessionShell", () => {
  it("renders loading state", () => {
    render(<SessionShell result={{ status: "loading" }} />);
    expect(screen.getByRole("main")).toHaveAttribute("aria-busy", "true");
  });

  it("offers login for an unauthenticated user", () => {
    render(<SessionShell result={{ status: "unauthenticated" }} />);
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/login?next=/app",
    );
  });

  it("renders the authenticated workspace", () => {
    render(
      <MemoryRouter>
        <SessionShell
          result={{
            status: "authenticated",
            session: {
              user: { id: "user-id", email: "max@example.test", name: "Max" },
              workspace: {
                id: "workspace-id",
                name: "Personal ledger",
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
            },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Personal ledger")).toBeInTheDocument();
    expect(screen.getByText("Max")).toBeInTheDocument();
    expect(screen.getByText("Владелец")).toBeInTheDocument();
    const mobileNavigation = screen.getByRole("navigation", {
      name: "Мобильная навигация",
    });
    expect(
      within(mobileNavigation).getByRole("link", { name: "Ручные операции" }),
    ).toHaveAttribute("href", "/ledger/manual");
  });

  it("renders a recoverable API error", () => {
    render(
      <SessionShell
        result={{ status: "error", message: "Backend недоступен." }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Backend недоступен.");
    expect(
      screen.getByRole("button", { name: "Повторить" }),
    ).toBeInTheDocument();
  });
});
