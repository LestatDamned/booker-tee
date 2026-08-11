import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { reportOverview, session } from "../features/reports/test-support";
import { ReportsRouteView } from "./reports";

describe("reports route", () => {
  it("renders visible currency, period semantics and archived filter facts", () => {
    renderReports();

    expect(screen.getByRole("heading", { name: "Отчёты" })).toBeVisible();
    expect(screen.getAllByLabelText(/120.*RUB/)[0]).toBeVisible();
    expect(screen.queryByText(/Балансы на/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Фильтры" }));
    expect(
      screen.getByRole("option", { name: "Архивный долларовый · USD · архив" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Квартира · архив" }),
    ).toBeInTheDocument();
  });

  it("shows the period outcome and reconciled account balances", () => {
    renderReports();

    const picture = screen.getByRole("region", {
      name: "Итог периода",
    });
    expect(within(picture).getByText("Положительный результат")).toBeVisible();
    expect(within(picture).getAllByText("На начало")[0]).toBeVisible();
    expect(within(picture).getAllByText("На конец")[0]).toBeVisible();

    const accountsRegion = screen.getByRole("region", {
      name: "Распределение денег по счетам",
    });
    const accounts = within(accountsRegion).getByRole("list", {
      name: "Остатки по счетам за период",
    });
    const accountLink = within(accounts).getByRole("link", {
      name: "Открыть операции счёта «Основной»",
    });
    const accountRow = accountLink.closest("li")!;
    expect(accountRow).toHaveTextContent(/110.*000,00/);
    expect(accountRow).toHaveTextContent(/185.*000,00/);
    expect(accountRow).toHaveTextContent(/\+75.*000,00/);
    const accountHref = new URL(
      accountLink.getAttribute("href")!,
      "http://localhost",
    );
    expect(accountHref.pathname).toBe(
      `/app/accounts/${reportOverview.accountBalances[0]!.accountId}`,
    );
    expect(accountHref.searchParams.get("date_from")).toBe("2026-07-01");
    expect(accountHref.searchParams.get("date_to")).toBe("2026-07-31");
    expect(accountHref.searchParams.get("status")).toBe("confirmed");
    expect(accountHref.searchParams.get("return_to")).toBe(
      "/app/reports?date_from=2026-07-01&date_to=2026-07-31&currency=RUB",
    );
  });

  it("keeps long account balances in compact records instead of a wide table", () => {
    const accountBalances = [
      ["ВТБ вклад", "1326326.24", "0.00", "-1326326.24"],
      ["Наличка", "10000.00", "29000.00", "19000.00"],
      ["Озон Банк вклад", "0.00", "1271395.00", "1271395.00"],
      ["Экспобанк карта", "13973.23", "5475.47", "-8497.76"],
    ].map(([name, openingBalance, closingBalance, balanceChange], index) => ({
      ...reportOverview.accountBalances[0]!,
      accountId: `wide-account-${index + 1}`,
      name: name!,
      openingBalance: openingBalance!,
      closingBalance: closingBalance!,
      balanceChange: balanceChange!,
    }));

    renderReports({ overview: { ...reportOverview, accountBalances } });

    const accounts = screen.getByRole("list", {
      name: "Остатки по счетам за период",
    });
    expect(within(accounts).getAllByRole("listitem")).toHaveLength(4);
    expect(
      screen.queryByRole("table", { name: "Остатки по счетам за период" }),
    ).not.toBeInTheDocument();
    expect(within(accounts).getAllByText(/1.*326.*326,24/)[0]).toBeVisible();
    expect(within(accounts).getAllByText(/1.*271.*395,00/)[0]).toBeVisible();
  });

  it("keeps the summary first and gives category analysis priority over accounts", () => {
    renderReports();

    const summary = screen.getByRole("region", { name: "Итог периода" });
    const categories = screen.getByRole("region", {
      name: "Деньги по категориям",
    });
    const accounts = screen.getByRole("region", {
      name: "Распределение денег по счетам",
    });

    expect(
      summary.compareDocumentPosition(categories) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      categories.compareDocumentPosition(accounts) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
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
      "/app/auth/login?next=%2Fapp%2Freports",
    );
  });

  it("shows both directions and result for every category on one common matrix", () => {
    renderReports();

    const matrix = screen.getByRole("table", {
      name: "Поступления, расходы и итог по категориям",
    });
    const matrixRows = within(matrix).getAllByRole("row");
    expect(matrixRows).toHaveLength(4);
    expect(
      within(matrix).getByRole("link", {
        name: "Категория: сортировать по возрастанию",
      }),
    ).toBeVisible();
    expect(
      within(matrix).getByRole("link", {
        name: "Поступления: сортировать по убыванию",
      }),
    ).toBeVisible();
    expect(
      within(matrix).getByRole("link", {
        name: "Расходы: сортировать по убыванию",
      }),
    ).toBeVisible();
    expect(
      within(matrix).getByRole("link", {
        name: "Итог: сортировать по убыванию",
      }),
    ).toBeVisible();
    expect(screen.queryByText(/Все суммы в/)).not.toBeInTheDocument();
    expect(screen.queryByText("Сначала")).not.toBeInTheDocument();
    expect(
      within(matrix).getByRole("row", { name: /^Итого/ }),
    ).toHaveTextContent(/120.*000,00.*−45.*000,00.*\+75.*000,00/);

    const bidirectional = within(matrix).getByRole("row", {
      name: /Продукты · архив/,
    });
    expect(matrixRows[1]).toBe(bidirectional);
    expect(bidirectional).toHaveTextContent(
      /120.*000,00.*RUB.*−5.*000,00.*RUB.*\+115.*000,00.*RUB/,
    );

    const expenseOnly = within(matrix)
      .getAllByRole("row")
      .find((row) =>
        within(row).queryByRole("link", {
          name: "Открыть все операции категории «Продукты»",
        }),
      )!;
    expect(expenseOnly).toHaveTextContent(
      /0,00.*RUB.*−40.*000,00.*RUB.*−40.*000,00.*RUB/,
    );
    expect(matrix.querySelector('[style*="width"]')).not.toBeInTheDocument();
    const categoryHref = new URL(
      within(expenseOnly)
        .getByRole("link", {
          name: "Открыть все операции категории «Продукты»",
        })
        .getAttribute("href")!,
      "http://localhost",
    );
    expect(categoryHref.pathname).toBe(
      `/app/categories/${reportOverview.categoryRows[0]!.categoryId}`,
    );
    expect(categoryHref.searchParams.get("date_from")).toBe("2026-07-01");
    expect(categoryHref.searchParams.get("date_to")).toBe("2026-07-31");
    expect(categoryHref.searchParams.get("currency")).toBe("RUB");
    expect(categoryHref.searchParams.has("type")).toBe(false);
    expect(categoryHref.searchParams.get("return_to")).toBe(
      "/app/reports?date_from=2026-07-01&date_to=2026-07-31&currency=RUB",
    );
    expect(screen.queryByText(/Показать все/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "Показатель отчёта" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "Раздел отчёта" }),
    ).not.toBeInTheDocument();
  });

  it("keeps matrix sorting in the URL and updates the row order", () => {
    renderReports({
      initialEntry:
        "/reports?date_from=2026-07-01&date_to=2026-07-31&currency=RUB&category_sort=expense",
    });

    expect(
      screen.getByRole("columnheader", {
        name: "Расходы: сортировать по возрастанию",
      }),
    ).toHaveAttribute("aria-sort", "descending");

    let matrix = screen.getByRole("table", {
      name: "Поступления, расходы и итог по категориям",
    });
    expect(within(matrix).getAllByRole("row")[1]).toHaveAccessibleName(
      /Открыть все операции категории «Продукты»/,
    );

    fireEvent.click(
      within(matrix).getByRole("link", {
        name: "Итог: сортировать по убыванию",
      }),
    );
    expect(
      screen.getByRole("link", {
        name: "Итог: сортировать по возрастанию",
      }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("columnheader", {
        name: "Итог: сортировать по возрастанию",
      }),
    ).toHaveAttribute("aria-sort", "descending");

    matrix = screen.getByRole("table", {
      name: "Поступления, расходы и итог по категориям",
    });
    const firstCategoryRow = within(matrix).getAllByRole("row")[1]!;
    expect(firstCategoryRow).toHaveAccessibleName(
      /Открыть все операции категории «Продукты · архив»/,
    );
    const drilldown = within(firstCategoryRow).getByRole("link", {
      name: "Открыть все операции категории «Продукты · архив»",
    });
    expect(decodeURIComponent(drilldown.getAttribute("href")!)).toContain(
      "return_to=/app/reports?date_from=2026-07-01&date_to=2026-07-31&currency=RUB&category_sort=result",
    );

    fireEvent.click(
      screen.getByRole("link", {
        name: "Итог: сортировать по возрастанию",
      }),
    );
    expect(
      screen.getByRole("columnheader", {
        name: "Итог: сортировать по убыванию",
      }),
    ).toHaveAttribute("aria-sort", "ascending");
    matrix = screen.getByRole("table", {
      name: "Поступления, расходы и итог по категориям",
    });
    expect(within(matrix).getAllByRole("row")[1]).toHaveAccessibleName(
      /Открыть все операции категории «Продукты»/,
    );

    fireEvent.click(
      screen.getByRole("link", {
        name: "Категория: сортировать по возрастанию",
      }),
    );
    expect(
      screen.getByRole("columnheader", {
        name: "Категория: сортировать по убыванию",
      }),
    ).toHaveAttribute("aria-sort", "ascending");
  });

  it("keeps the headline, category flows and account balances reconciled", () => {
    const categoryIncome = reportOverview.categoryRows.reduce(
      (total, row) => total + Number(row.income),
      0,
    );
    const categoryExpense = reportOverview.categoryRows.reduce(
      (total, row) => total + Number(row.expense),
      0,
    );
    const openingBalance = reportOverview.accountBalances.reduce(
      (total, row) => total + Number(row.openingBalance),
      0,
    );
    const closingBalance = reportOverview.accountBalances.reduce(
      (total, row) => total + Number(row.closingBalance),
      0,
    );

    expect(categoryIncome).toBe(Number(reportOverview.summary.income));
    expect(categoryExpense).toBe(Number(reportOverview.summary.expense));
    expect(categoryIncome - categoryExpense).toBe(
      Number(reportOverview.summary.profit),
    );
    expect(openingBalance).toBe(
      Number(reportOverview.balanceSummary.openingBalance),
    );
    expect(closingBalance).toBe(
      Number(reportOverview.balanceSummary.closingBalance),
    );
    expect(closingBalance - openingBalance).toBe(
      Number(reportOverview.balanceSummary.balanceChange),
    );
  });

  it("shows zero result and negative archived account balances without hiding facts", () => {
    const archivedAccount = {
      ...reportOverview.accountBalances[0]!,
      accountId: "archived-negative-account",
      name: "Архивный накопительный счёт с очень длинным названием",
      openingBalance: "-1500.00",
      closingBalance: "-2500.00",
      balanceChange: "-1000.00",
      isActive: false,
    };
    renderReports({
      overview: {
        ...reportOverview,
        summary: {
          ...reportOverview.summary,
          income: "0.00",
          expense: "0.00",
          profit: "0.00",
        },
        balanceSummary: {
          ...reportOverview.balanceSummary,
          openingBalance: "-1500.00",
          closingBalance: "-2500.00",
          balanceChange: "-1000.00",
        },
        accountBalances: [archivedAccount],
        categoryRows: [],
      },
    });

    expect(screen.getByText("Доходы и расходы равны")).toBeVisible();
    const periodSummary = document.querySelector<HTMLElement>(
      '[data-report-period-summary="true"]',
    );
    expect(periodSummary).not.toBeNull();
    expect(
      within(periodSummary!).getByRole("region", {
        name: "Денежный поток",
      }),
    ).toHaveTextContent(/Доходы.*0,00.*RUB.*Расходы.*0,00.*RUB/);
    expect(periodSummary).not.toHaveTextContent(/[+−]0,00/);
    expect(screen.queryByLabelText("+0,00 RUB")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("−0,00 RUB")).not.toBeInTheDocument();
    const accountRow = screen
      .getByRole("link", {
        name: "Открыть операции счёта «Архивный накопительный счёт с очень длинным названием · архив»",
      })
      .closest("li")!;
    expect(accountRow).toHaveTextContent(/−1.*500,00/);
    expect(accountRow).toHaveTextContent(/−2.*500,00/);
    expect(accountRow).toHaveTextContent(/−1.*000,00/);
    expect(
      screen.getByText(
        "За выбранный период нет доходов или расходов по категориям.",
      ),
    ).toBeVisible();
  });

  it("keeps every category visible when a ranked list is long", () => {
    const categoryRows = Array.from({ length: 12 }, (_, index) => ({
      ...reportOverview.categoryRows[0]!,
      categoryId: `category-${index + 1}`,
      name: `Категория ${index + 1}`,
      expense: `${12000 - index * 500}.00`,
      profit: `-${12000 - index * 500}.00`,
    }));
    renderReports({
      overview: {
        ...reportOverview,
        categoryRows,
      },
    });

    const matrix = screen.getByRole("table", {
      name: "Поступления, расходы и итог по категориям",
    });
    expect(within(matrix).getAllByRole("row")).toHaveLength(14);
    expect(within(matrix).getByText("Категория 12")).toBeVisible();
    expect(screen.queryByText(/Показать все/)).not.toBeInTheDocument();
  });

  it("marks the actual period preset instead of always selecting this month", () => {
    renderReports({
      initialEntry: "/reports?currency=RUB",
      overview: {
        ...reportOverview,
        appliedFilters: {
          ...reportOverview.appliedFilters,
          dateFrom: null,
          dateTo: null,
        },
      },
    });

    expect(screen.getByRole("link", { name: "Всё время" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("link", { name: "Этот месяц" }),
    ).not.toHaveAttribute("aria-current");
    expect(
      screen.getByRole("button", { name: "Скачать отчёт" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("group", {
        name: "Выберите полный месяц, чтобы скачать отчёт",
      }),
    ).toHaveAttribute("title", "Выберите полный месяц, чтобы скачать отчёт");
  });

  it("downloads the selected full month without client-side report data", () => {
    renderReports();

    expect(screen.getByRole("link", { name: "Скачать отчёт" })).toHaveAttribute(
      "href",
      "/api/v1/reports/export.xlsx?month=2026-07&currency=RUB",
    );
  });

  it("shows one clear matrix empty state when the category structure is empty", () => {
    renderReports({
      overview: { ...reportOverview, categoryRows: [], propertyRows: [] },
    });

    expect(
      screen.getByText(
        "За выбранный период нет доходов или расходов по категориям.",
      ),
    ).toBeVisible();
  });

  it("compresses uncategorized operations into one actionable notice", () => {
    renderReports();

    expect(screen.getByText("12 операций без категории")).toBeVisible();
    expect(screen.getByRole("link", { name: "Разобрать" })).toHaveAttribute(
      "href",
      `/operations?operation_id=${reportOverview.uncategorized.items[0]!.operationId}#operation-${reportOverview.uncategorized.items[0]!.operationId}`,
    );
    expect(
      screen.queryByRole("table", { name: "Операции без категории" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", {
        name: "Страницы операций без категории",
      }),
    ).not.toBeInTheDocument();

    const breakdowns = screen.getByRole("region", {
      name: "Деньги по категориям",
    });
    const notice = screen
      .getByText("12 операций без категории")
      .closest('[data-tone="warning"]');
    expect(notice).not.toBeNull();
    expect(
      breakdowns.compareDocumentPosition(notice!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("hides the notice when all matching operations are categorized", () => {
    renderReports({
      overview: {
        ...reportOverview,
        uncategorized: {
          ...reportOverview.uncategorized,
          items: [],
          total: 0,
          totalPages: 1,
          hasNext: false,
        },
      },
    });

    expect(screen.queryByText(/без категории$/)).not.toBeInTheDocument();
  });

  it("uses the unified operation workflow for a correctable import", () => {
    const imported = reportOverview.uncategorized.items[1]!;
    renderReports({
      overview: {
        ...reportOverview,
        uncategorized: {
          ...reportOverview.uncategorized,
          items: [
            {
              ...imported,
              capabilities: { canCorrect: true, readonlyReasonCode: null },
            },
          ],
          total: 1,
          totalPages: 1,
          hasNext: false,
        },
      },
    });

    expect(screen.getByRole("link", { name: "Разобрать" })).toHaveAttribute(
      "href",
      `/operations?operation_id=${imported.operationId}#operation-${imported.operationId}`,
    );
  });
});

function renderReports({
  initialEntry = "/reports?date_from=2026-07-01&date_to=2026-07-31&currency=RUB",
  overview = reportOverview,
}: {
  initialEntry?: string;
  overview?: typeof reportOverview;
} = {}) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ReportsRouteView
        loaderData={{
          session: { status: "authenticated", session },
          reports: { status: "success", overview },
        }}
      />
    </MemoryRouter>,
  );
}
