import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("renders workspace navigation and closes the mobile menu with Escape", async () => {
    const user = userEvent.setup();
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

    expect(
      screen.getByRole("link", { name: "Перейти к содержимому" }),
    ).toHaveAttribute("href", "#app-main-content");
    expect(screen.getByRole("main")).toHaveAttribute("id", "app-main-content");
    expect(screen.getByRole("main")).toHaveAttribute("tabindex", "-1");

    const sidebar = screen.getByRole("complementary");
    expect(
      within(sidebar).getByRole("link", {
        name: "Текущий workspace: Personal ledger. Открыть пространства",
      }),
    ).toHaveAttribute("href", "/workspaces");
    expect(
      within(sidebar).getByRole("link", {
        name: "Max. Владелец. Открыть профиль",
      }),
    ).toHaveAttribute("href", "/users");
    expect(
      within(screen.getByRole("main")).queryByText("Текущий workspace"),
    ).not.toBeInTheDocument();

    const desktopNavigation = within(sidebar).getByRole("navigation", {
      name: "Главная навигация",
    });
    expect(
      within(desktopNavigation).getByRole("link", { name: "Счета" }),
    ).toHaveAttribute("href", "/accounts");
    expect(
      within(desktopNavigation).getByRole("link", { name: "Отчёты" }),
    ).toHaveAttribute("href", "/reports");
    expect(
      within(desktopNavigation).getByRole("link", { name: "Категории" }),
    ).toHaveAttribute("href", "/categories");
    expect(
      within(desktopNavigation).getByRole("link", { name: "Объекты" }),
    ).toHaveAttribute("href", "/properties");
    expect(
      within(desktopNavigation).getByRole("link", { name: "Правила" }),
    ).toHaveAttribute("href", "/rules");

    const mobileNavigation = screen.getByRole("navigation", {
      name: "Мобильная навигация",
    });
    expect(
      within(mobileNavigation).getByRole("link", { name: "Ручные операции" }),
    ).toHaveAttribute("href", "/ledger/manual");

    const menuSummary = screen.getByText("Меню").closest("summary");
    const mobileMenu = menuSummary?.closest("details");
    if (!menuSummary || !mobileMenu) {
      throw new Error("Mobile menu disclosure was not rendered.");
    }
    await user.click(menuSummary);
    expect(mobileMenu).toHaveAttribute("open");
    menuSummary.focus();
    await user.keyboard("{Escape}");
    expect(mobileMenu).not.toHaveAttribute("open");
    expect(menuSummary).toHaveFocus();
  });

  it("renders a recoverable API error", () => {
    render(
      <SessionShell
        result={{ status: "error", message: "Backend недоступен." }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Backend недоступен.");
    expect(screen.getByRole("link", { name: "Повторить" })).toHaveAttribute(
      "href",
      "/app",
    );
  });
});
