import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { SessionDto } from "../../api/session";
import type { PropertyDirectoryDto } from "./api/properties-api";
import { PropertiesPage } from "./properties-page";

describe("PropertiesPage", () => {
  it("renders active properties with status counts and property-scoped reports", () => {
    renderPage(directory);

    expect(screen.getByRole("heading", { name: "Объекты" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Активные 1" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Архив 1" })).toBeVisible();
    expect(screen.getAllByText("Квартира")).toHaveLength(2);
    expect(screen.getAllByText("Активен")).toHaveLength(2);
    expect(screen.getAllByText("Красноярск, ул. Мира, 1")).toHaveLength(2);
    expect(
      screen.getAllByRole("link", {
        name: "Открыть отчёт по объекту «Квартира»",
      })[0],
    ).toHaveAttribute("href", `/reports?property_id=${directory.items[0]!.id}`);
  });

  it("shows archived objects from URL state", () => {
    renderPage(directory, "/properties?view=archived");

    expect(screen.getByRole("link", { name: "Архив 1" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getAllByText("Старый проект")).toHaveLength(2);
    expect(
      screen
        .getAllByText("Архив")
        .filter((label) => label.closest("[data-tone='neutral']")),
    ).toHaveLength(2);
    expect(screen.queryByText("Квартира")).not.toBeInTheDocument();
  });

  it("searches visible properties and offers one reset path", async () => {
    const user = userEvent.setup();
    renderPage(directory);

    await user.type(
      screen.getByRole("searchbox", {
        name: "Поиск по названию, короткому названию или адресу",
      }),
      "офис",
    );
    await user.click(screen.getByRole("button", { name: "Найти" }));

    expect(
      screen.getByRole("heading", { name: "По этому запросу объектов нет" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Очистить поиск" })).toBeVisible();
  });

  it("keeps a viewer readable without implying mutation authority", () => {
    renderPage({
      ...directory,
      capabilities: {
        canCreate: false,
        readonlyReasonCode: "financial_write_forbidden",
      },
      items: directory.items.map((property) => ({
        ...property,
        capabilities: {
          canUpdate: false,
          canArchive: false,
          canRestore: false,
        },
      })),
    });

    expect(
      screen.getByText("Объекты доступны только для просмотра"),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /Новый объект/ })).toBeNull();
  });
});

function renderPage(
  currentDirectory: PropertyDirectoryDto,
  initialEntry = "/properties",
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <PropertiesPage directory={currentDirectory} session={session} />
    </MemoryRouter>,
  );
}

const directory: PropertyDirectoryDto = {
  items: [
    {
      id: "285c18d8-78bb-46d7-b6cd-d6fc897ab8a2",
      name: "Квартира",
      shortName: "Дом",
      address: "Красноярск, ул. Мира, 1",
      status: "active",
      archivedAt: null,
      updatedAt: "2026-08-01T08:30:00Z",
      capabilities: {
        canUpdate: true,
        canArchive: true,
        canRestore: false,
      },
    },
    {
      id: "1b7ba3c1-1af5-4dce-ab51-594adef47c48",
      name: "Старый проект",
      shortName: null,
      address: null,
      status: "archived",
      archivedAt: "2026-08-01T08:30:00Z",
      updatedAt: "2026-08-01T08:30:00Z",
      capabilities: {
        canUpdate: true,
        canArchive: false,
        canRestore: true,
      },
    },
  ],
  capabilities: { canCreate: true, readonlyReasonCode: null },
};

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
