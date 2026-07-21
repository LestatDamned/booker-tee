import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportReviewPage } from "./import-review-page";
import {
  expenseCategoryId,
  importReviewPayload,
  remainingItemId,
} from "./test-support";

describe("import review page", () => {
  afterEach(() => vi.unstubAllGlobals());
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

  it("keeps the local row draft after a network error and panel toggle", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline"))),
    );
    renderPage(importReviewPayload());

    const summary = screen.getByText("Разобрать строку");
    await user.click(summary);
    const category = screen.getByLabelText("Категория");
    await user.selectOptions(category, expenseCategoryId);
    await user.click(screen.getByRole("button", { name: "Проверить выбор" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Backend недоступен",
    );
    await user.click(summary);
    await user.click(summary);
    expect(screen.getByLabelText("Категория")).toHaveValue(expenseCategoryId);
  });

  it("keeps invalid category input and focuses the first invalid field", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "invalid_category",
                message: "Категорию не удалось создать.",
                fieldErrors: { name: ["Название уже занято."] },
              },
            }),
            { status: 422 },
          ),
        ),
      ),
    );
    renderPage(importReviewPayload());

    await user.click(screen.getByText("Разобрать строку"));
    await user.click(screen.getByRole("button", { name: "Новая категория" }));
    const name = screen.getByLabelText("Название категории");
    await user.type(name, "Продукты");
    await user.click(screen.getByRole("button", { name: "Создать и выбрать" }));

    expect(await screen.findByText("Название уже занято.")).toBeInTheDocument();
    expect(name).toHaveValue("Продукты");
    expect(name).toHaveFocus();
  });

  it("reconciles the row and queue only from the committed transfer response", async () => {
    const user = userEvent.setup();
    const updated = importReviewPayload();
    const item = updated.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.status = "confirmed";
    item.isTerminal = true;
    item.isReviewable = false;
    updated.queue.completed = 2;
    updated.queue.remaining = 0;
    updated.queue.firstRemainingItemId = null;
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            primaryDocumentId: updated.document.id,
            updatedItemIds: [remainingItemId],
            validationDocumentIds: [updated.document.id],
            reviews: [updated],
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage(importReviewPayload());

    const reviewPanel = screen.getAllByText("Разобрать строку")[0];
    if (!reviewPanel) throw new Error("review panel is required");
    await user.click(reviewPanel);
    await user.selectOptions(screen.getByLabelText("Тип операции"), "transfer");
    expect(
      screen.getByText("Основной счёт → выбранный счёт"),
    ).toBeInTheDocument();
    await user.selectOptions(
      screen.getByLabelText("Сопоставление"),
      "account:c145935c-67c6-4bf6-a0ce-64e5d611cf47",
    );
    await user.click(screen.getByRole("button", { name: "Провести перевод" }));

    expect(
      await screen.findByRole("heading", { name: "Все строки обработаны" }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/items/${remainingItemId}/transfer`),
      expect.objectContaining({
        headers: expect.objectContaining({
          "Idempotency-Key": expect.any(String),
        }),
      }),
    );
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
