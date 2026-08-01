import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { CategoryDetailPage } from "./category-detail-page";
import { detail, session } from "./test-support";

describe("CategoryDetailPage", () => {
  it("renders currency-safe summary, bounded operations and rules preview", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Продукты" })).toBeVisible();
    expect(screen.getByLabelText(/100.*000,00 RUB/)).toBeVisible();
    expect(screen.getAllByLabelText(/35.*000,00 RUB/)[0]).toBeVisible();
    expect(screen.getByLabelText(/65.*000,00 RUB/)).toBeVisible();
    expect(screen.getByText("Супермаркет")).toBeVisible();
    expect(screen.getByText("Не влияет на прибыль")).toBeVisible();
    expect(screen.getByText("1–20 из 22")).toBeVisible();
    expect(screen.getByRole("link", { name: "Страница 2" })).toHaveAttribute(
      "href",
      expect.stringContaining("operations_page=2"),
    );
    expect(
      screen.getByRole("heading", { name: "Связанные правила" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Супермаркеты" })).toHaveAttribute(
      "href",
      `/rules#rule-${detail.rules.items[0]!.id}`,
    );
  });

  it("treats the workspace currency default as context, not an active filter", () => {
    renderPage("/categories/id", {
      ...detail,
      appliedFilters: {
        ...detail.appliedFilters,
        dateFrom: null,
        dateTo: null,
      },
    });

    expect(screen.queryByText("Активные фильтры")).not.toBeInTheDocument();
  });

  it("preserves a safe Reports back path and rejects an external one", () => {
    const { unmount } = renderPage(
      "/categories/id?currency=RUB&return_to=%2Fapp%2Freports%3Fcurrency%3DRUB",
    );
    expect(
      screen.getByRole("link", { name: "Вернуться в отчёт" }),
    ).toHaveAttribute("href", "/app/reports?currency=RUB");
    expect(screen.getByText("Валюта: RUB")).toBeVisible();
    unmount();

    renderPage(
      "/categories/id?return_to=https%3A%2F%2Fevil.test%2Fapp%2Freports",
    );
    expect(screen.getByRole("link", { name: "Все категории" })).toHaveAttribute(
      "href",
      "/categories",
    );
  });

  it("applies detail filters and retains report context", async () => {
    const user = userEvent.setup();
    renderPage("/categories/id?return_to=%2Fapp%2Freports%3Fcurrency%3DRUB");

    await user.click(screen.getByRole("button", { name: /Показать фильтры/ }));
    await user.clear(screen.getByLabelText("Дата от"));
    await user.type(screen.getByLabelText("Дата от"), "2026-08-01");
    await user.selectOptions(screen.getByLabelText("Валюта"), "USD");
    await user.selectOptions(screen.getByLabelText("Тип операции"), "expense");
    await user.click(screen.getByRole("button", { name: "Применить" }));

    expect(screen.getByTestId("location")).toHaveTextContent(
      "date_from=2026-08-01",
    );
    expect(screen.getByTestId("location")).toHaveTextContent("currency=USD");
    expect(screen.getByTestId("location")).toHaveTextContent("type=expense");
    expect(screen.getByTestId("location")).toHaveTextContent(
      "return_to=%2Fapp%2Freports%3Fcurrency%3DRUB",
    );
    expect(screen.getByTestId("location")).not.toHaveTextContent(
      "operations_page=",
    );
  });

  it("searches operations without dropping filters or report context", async () => {
    const user = userEvent.setup();
    renderPage(
      "/categories/id?currency=RUB&type=expense&operations_page=2&return_to=%2Fapp%2Freports",
    );

    await user.type(
      screen.getByRole("searchbox", {
        name: "Поиск по описанию операции",
      }),
      "  market  ",
    );
    await user.click(screen.getByRole("button", { name: "Найти" }));

    const location = screen.getByTestId("location");
    expect(location).toHaveTextContent("search=market");
    expect(location).toHaveTextContent("currency=RUB");
    expect(location).toHaveTextContent("type=expense");
    expect(location).toHaveTextContent("return_to=%2Fapp%2Freports");
    expect(location).not.toHaveTextContent("operations_page=");
  });

  it("changes page size and resets operation pagination", async () => {
    const user = userEvent.setup();
    renderPage("/categories/id?currency=RUB&operations_page=2");

    await user.selectOptions(screen.getByLabelText("На странице"), "50");

    const location = screen.getByTestId("location");
    expect(location).toHaveTextContent("currency=RUB");
    expect(location).toHaveTextContent("operations_page_size=50");
    expect(location).not.toHaveTextContent("operations_page=2");
  });
});

function renderPage(initialEntry = "/categories/id", categoryDetail = detail) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <CategoryDetailPage detail={categoryDetail} session={session} />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.pathname}
      {location.search}
    </output>
  );
}
