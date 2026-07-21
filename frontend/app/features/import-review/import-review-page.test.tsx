import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { ImportReviewPage } from "./import-review-page";
import { importReviewPayload, remainingItemId } from "./test-support";

describe("import review page", () => {
  it("renders queue progress and links to the first remaining row", () => {
    renderPage(importReviewPayload());

    expect(
      screen.getByRole("heading", { name: "Осталось 1 из 2" }),
    ).toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "К первой оставшейся строке" }),
    ).toHaveAttribute("href", `#raw-${remainingItemId}`);
    expect(document.getElementById(`raw-${remainingItemId}`)).not.toBeNull();
    expect(screen.getByText("Проверено как уникальное")).toBeInTheDocument();
  });

  it("shows raw source values without replacing normalized facts", () => {
    renderPage(importReviewPayload());

    expect(screen.getAllByText("-1250.50")).toHaveLength(2);
    expect(screen.getAllByText("Исходные данные")).toHaveLength(2);
    expect(screen.getAllByText("-1250,50")).toHaveLength(2);
    expect(screen.getAllByText("*1234")).toHaveLength(2);
  });

  it("renders typed validation totals and a problem on the stable row anchor", () => {
    renderPage(importReviewPayload());

    expect(
      screen.getByRole("heading", { name: "Нарушена цепочка остатков" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("table", {
        name: "Суммы строк и контрольные итоги выписки",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/обнаружено несоответствий: 1; проверено пар: 1/),
    ).toBeInTheDocument();
    const row = document.getElementById(`raw-${remainingItemId}`);
    expect(row).toHaveTextContent("После строки 1 ожидался остаток");
    expect(row).toHaveTextContent("10050.50 RUB");
  });

  it("explains unavailable totals without hiding raw rows", () => {
    const review = importReviewPayload();
    if (!review.validation) throw new Error("validation fixture is required");
    review.validation.status = "unavailable";
    review.validation.reasonCode = "control_totals_unavailable";
    review.validation.statementTotalInflow = null;
    review.validation.statementTotalOutflow = null;
    review.validation.rowProblems = [];

    renderPage(review);

    expect(
      screen.getByRole("heading", { name: "Контрольные итоги недоступны" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Исходные данные")).toHaveLength(2);
  });

  it("distinguishes a mismatch explained by ignored rows", () => {
    const review = importReviewPayload();
    if (!review.validation) throw new Error("validation fixture is required");
    review.validation.reasonCode = "ignored_rows_explain_mismatch";
    review.validation.ignoredTotalOutflow = "50.50";
    review.validation.unexplainedOutflowDifference = "0.00";
    review.validation.rowProblems = [];

    renderPage(review);

    expect(
      screen.getByRole("heading", {
        name: "Разница объясняется игнорируемыми строками",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("50.50 RUB")).toBeInTheDocument();
  });

  it("renders an explicit empty queue", () => {
    const review = importReviewPayload();
    review.items = [];
    review.queue = {
      total: 0,
      completed: 0,
      remaining: 0,
      firstRemainingItemId: null,
      orderedItemIds: [],
    };

    renderPage(review);

    expect(
      screen.getByRole("heading", { name: "Строк для проверки пока нет" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Сырых строк пока нет")).toBeInTheDocument();
  });

  it("renders a completed queue without a next-row link", () => {
    const review = importReviewPayload();
    review.queue = {
      ...review.queue,
      completed: 2,
      remaining: 0,
      firstRemainingItemId: null,
    };

    renderPage(review);

    expect(
      screen.getByRole("heading", { name: "Все строки обработаны" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "К первой оставшейся строке" }),
    ).not.toBeInTheDocument();
  });

  it("explains readonly access", () => {
    const review = importReviewPayload();
    review.capabilities = {
      canWrite: false,
      readonlyReasonCode: "financial_write_forbidden",
    };

    renderPage(review);

    expect(screen.getByText(/доступен только для чтения/)).toBeInTheDocument();
  });
});

function renderPage(review: ReturnType<typeof importReviewPayload>) {
  render(
    <MemoryRouter>
      <ImportReviewPage review={review} session={sessionPayload} />
    </MemoryRouter>,
  );
}

const sessionPayload = {
  user: {
    id: "f4835818-f111-41d6-a59d-62f541ace357",
    email: "max@example.test",
    name: "Max",
  },
  workspace: {
    id: "c12c9ac8-6851-4467-b87a-da7fc70586c8",
    name: "Дом",
    type: "personal" as const,
    defaultCurrency: "RUB",
  },
  membership: { role: "owner" as const, status: "active" as const },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canManageMembers: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};
