import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { reportOverview, session } from "../features/reports/test-support";
import { ReportsRouteView } from "./reports";

describe("reports route", () => {
  it("renders visible currency, period semantics and archived filter facts", () => {
    render(
      <MemoryRouter initialEntries={["/reports?currency=RUB"]}>
        <ReportsRouteView
          loaderData={{
            session: { status: "authenticated", session },
            reports: { status: "success", overview: reportOverview },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Отчёты" })).toBeVisible();
    expect(screen.getAllByLabelText(/120.*RUB/)[0]).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Балансы на 31.07.2026" }),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Точные фильтры" }));
    expect(
      screen.getByRole("option", { name: "Архивный долларовый · USD · архив" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Квартира · архив" }),
    ).toBeInTheDocument();
  });

  it("renders a stable login recovery path", () => {
    render(
      <MemoryRouter>
        <ReportsRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            reports: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/login?next=/app/reports",
    );
  });

  it("renders distinct category and property identities with exact money facts", () => {
    renderReports();

    const categoryTable = screen.getByRole("table", {
      name: "Доходы, расходы и прибыль по категориям",
    });
    const categoryRows = within(categoryTable).getAllByRole("row");
    expect(categoryRows).toHaveLength(3);
    expect(
      categoryRows.filter((row) => row.textContent?.includes("Продукты")),
    ).toHaveLength(2);
    expect(
      categoryRows.some((row) => row.textContent?.includes("Продукты · архив")),
    ).toBe(true);
    expect(
      within(categoryTable).getByRole("link", { name: "Продукты" }),
    ).toHaveAttribute(
      "href",
      `/categories/${reportOverview.categoryRows[0]!.categoryId}?date_from=2026-07-01&date_to=2026-07-31`,
    );

    const propertyTable = screen.getByRole("table", {
      name: "Доходы, расходы и прибыль по объектам",
    });
    const propertyRows = within(propertyTable).getAllByRole("row");
    expect(propertyRows).toHaveLength(3);
    expect(propertyRows[1]).toHaveTextContent("Квартира");
    expect(propertyRows[2]).toHaveTextContent("Квартира · архив");
    expect(propertyRows[2]).toHaveTextContent(/10.*000,00.*RUB/);
  });

  it("publishes category sorting through URL and aria-sort", () => {
    renderReports({ withLocation: true });

    const categoryTable = screen.getByRole("table", {
      name: "Доходы, расходы и прибыль по категориям",
    });
    expect(
      within(categoryTable).getByRole("columnheader", { name: /Категория/ }),
    ).toHaveAttribute("aria-sort", "ascending");
    fireEvent.click(
      within(categoryTable).getByRole("link", {
        name: "Расходы. Сортировать по убыванию",
      }),
    );

    expect(screen.getByTestId("location")).toHaveTextContent(
      "category_sort=expense&category_sort_dir=desc",
    );
    expect(
      within(categoryTable).getByRole("columnheader", { name: /Расходы/ }),
    ).toHaveAttribute("aria-sort", "descending");
    expect(within(categoryTable).getAllByRole("row")[1]).toHaveTextContent(
      /45.*000,00/,
    );
    expect(
      within(
        screen.getByRole("navigation", { name: "Сортировка категорий" }),
      ).getByRole("link", { name: /Сортировать категории: Расходы/ }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("explains empty category and property breakdowns separately", () => {
    renderReports({
      overview: { ...reportOverview, categoryRows: [], propertyRows: [] },
    });

    expect(screen.getByText("Нет данных по категориям")).toBeVisible();
    expect(screen.getByText("Нет данных по объектам")).toBeVisible();
  });
});

function renderReports({
  overview = reportOverview,
  withLocation = false,
}: {
  overview?: typeof reportOverview;
  withLocation?: boolean;
} = {}) {
  return render(
    <MemoryRouter
      initialEntries={[
        "/reports?date_from=2026-07-01&date_to=2026-07-31&currency=RUB",
      ]}
    >
      <ReportsRouteView
        loaderData={{
          session: { status: "authenticated", session },
          reports: { status: "success", overview },
        }}
      />
      {withLocation ? <LocationProbe /> : null}
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.search}</output>;
}
