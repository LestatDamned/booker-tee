import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
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
    expect(screen.getByLabelText(/120.*RUB/)).toBeVisible();
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
});
