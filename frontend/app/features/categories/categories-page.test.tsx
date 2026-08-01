import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { CategoriesPage } from "./categories-page";
import { directory, session } from "./test-support";

describe("CategoriesPage", () => {
  it("renders a compact active directory with semantic category facts", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Категории" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Активные 2" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Архив 1" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Системные 1" })).toBeVisible();
    expect(screen.getAllByText("Продукты")).toHaveLength(2);
    expect(screen.getAllByText("Расход")).toHaveLength(2);
    expect(screen.getAllByText("12 операций")).toHaveLength(2);
    expect(screen.getAllByText("1 активных")).toHaveLength(2);
    expect(
      screen.getAllByRole("link", { name: "Открыть категорию «Продукты»" })[0],
    ).toHaveAttribute("href", `/categories/${directory.items[0]!.id}`);
    expect(screen.queryByText("Старые покупки")).not.toBeInTheDocument();
    expect(screen.queryByText("Без категории")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Новая категория/ }),
    ).toBeNull();
  });

  it("shows archived and system records from URL state", () => {
    const { unmount } = renderPage("/categories?view=archived");
    expect(screen.getAllByText("Старые покупки")).toHaveLength(2);
    expect(
      screen
        .getAllByText("Архив")
        .filter((label) => label.closest("[data-tone='neutral']")),
    ).toHaveLength(2);
    unmount();

    renderPage("/categories?view=system");
    expect(screen.getAllByText("Без категории")).toHaveLength(2);
    expect(screen.getAllByText("Системная")).toHaveLength(2);
    expect(screen.getAllByText("Смешанная")).toHaveLength(2);
  });

  it("searches by localized kind and offers one reset path", async () => {
    const user = userEvent.setup();
    renderPage();

    const search = screen.getByRole("searchbox", {
      name: "Поиск по названию, типу или заметке",
    });
    await user.type(search, "перевод");
    await user.click(screen.getByRole("button", { name: "Найти" }));

    expect(
      screen.getByRole("heading", { name: "По этому запросу категорий нет" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Очистить поиск" })).toBeVisible();
  });

  it("keeps viewer access explicit without implying mutation authority", () => {
    renderPage("/categories", {
      ...directory,
      capabilities: {
        canCreate: false,
        readonlyReasonCode: "financial_write_forbidden",
      },
      items: directory.items.map((category) => ({
        ...category,
        capabilities: {
          canUpdate: false,
          canArchive: false,
          canRestore: false,
          archiveBlockedReasonCode:
            category.capabilities.archiveBlockedReasonCode,
        },
      })),
    });

    expect(
      screen.getByText("Категории доступны только для просмотра"),
    ).toBeVisible();
    expect(screen.getAllByText("Продукты")).toHaveLength(2);
  });
});

function renderPage(
  initialEntry = "/categories",
  categoryDirectory = directory,
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <CategoriesPage directory={categoryDirectory} session={session} />
    </MemoryRouter>,
  );
}
