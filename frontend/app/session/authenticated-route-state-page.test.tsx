import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuthenticatedRouteStatePage } from "./authenticated-route-state-page";

describe("AuthenticatedRouteStatePage", () => {
  it("renders the shared login state with an encoded return destination", () => {
    render(
      <AuthenticatedRouteStatePage
        errorTitle="Не удалось загрузить счета"
        result={{ status: "unauthenticated" }}
        returnTo="/app/accounts?status=active"
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Войдите в Booker Tee" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/app/auth/login?next=%2Fapp%2Faccounts%3Fstatus%3Dactive",
    );
  });

  it("renders a retryable alert with the feature error title and message", () => {
    render(
      <AuthenticatedRouteStatePage
        errorTitle="Не удалось загрузить отчёт"
        result={{ status: "error", message: "Backend недоступен." }}
        returnTo="/app/reports"
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Не удалось загрузить отчёт",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Backend недоступен.");
    expect(screen.getByRole("link", { name: "Повторить" })).toHaveAttribute(
      "href",
      "/app/reports",
    );
  });
});
