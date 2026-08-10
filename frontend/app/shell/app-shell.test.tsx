import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { session } from "../features/workspaces/test-support";
import { AppShell } from "./app-shell";

describe("AppShell role navigation", () => {
  it("hides raw imports from analysts but keeps reports", () => {
    render(
      <MemoryRouter>
        <AppShell
          session={{
            ...session,
            membership: { role: "analyst", status: "active" },
            capabilities: {
              ...session.capabilities,
              canManageImports: false,
              canViewRawImportData: false,
            },
          }}
        >
          Content
        </AppShell>
      </MemoryRouter>,
    );

    expect(
      screen.queryByRole("link", { name: "Импорты" }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Отчёты" })).toHaveLength(2);
  });

  it("shows raw imports to read-only viewers", () => {
    render(
      <MemoryRouter>
        <AppShell
          session={{
            ...session,
            membership: { role: "viewer", status: "active" },
            capabilities: {
              ...session.capabilities,
              canManageImports: false,
              canViewRawImportData: true,
            },
          }}
        >
          Content
        </AppShell>
      </MemoryRouter>,
    );

    expect(screen.getAllByRole("link", { name: "Импорты" })).toHaveLength(2);
  });
});
