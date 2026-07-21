import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportReviewPage } from "./import-review-page";
import {
  completedItemId,
  confirmedOperationId,
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
    expect(
      screen.queryByRole("button", { name: "Отменить проведение" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Применить правила" }),
    ).not.toBeInTheDocument();
  });

  it("applies document rules and reconciles all rows from the server", async () => {
    const user = userEvent.setup();
    const updated = importReviewPayload();
    const updatedItem = updated.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!updatedItem) throw new Error("remaining fixture item is required");
    updatedItem.ruleSuggestion = {
      isActive: true,
      wasAutoApplied: true,
      ruleId: "a6f780bd-fc27-448e-aa66-9f20c478fb4f",
    };
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            documentId: updated.document.id,
            checkedCount: 1,
            suggestedCount: 1,
            updatedItemIds: [remainingItemId],
            review: updated,
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage(importReviewPayload());

    await user.click(screen.getByRole("button", { name: "Применить правила" }));

    expect(
      await screen.findByText("Проверено строк: 1. Предложений применено: 1."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Правило предложило значения/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/apply-rules"),
      expect.objectContaining({ method: "POST" }),
    );
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

  it("requires danger confirmation and reconciles duplicate lifecycle", async () => {
    const user = userEvent.setup();
    const review = possibleDuplicateReview();
    const updated = possibleDuplicateReview();
    const item = updated.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.status = "duplicate";
    item.isTerminal = true;
    item.isReviewable = false;
    item.lifecycle.allowedActions = ["mark_unique", "needs_review", "ignore"];
    updated.document.status = "imported";
    updated.queue.completed = 2;
    updated.queue.remaining = 0;
    updated.queue.firstRemainingItemId = null;
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            itemId: remainingItemId,
            documentId: updated.document.id,
            replayed: false,
            review: updated,
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage(review);

    await user.click(screen.getByRole("button", { name: "Отметить дублем" }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText(/Пометить строку дублем/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отмена" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Подтвердить" }));

    expect(
      await screen.findByRole("heading", { name: "Все строки обработаны" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Дубль")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/lifecycle"),
      expect.objectContaining({
        body: JSON.stringify({
          action: "mark_duplicate",
          expectedStatus: "possible_duplicate",
        }),
      }),
    );
  });

  it("focuses a stale conflict and refreshes authoritative state", async () => {
    const user = userEvent.setup();
    const review = possibleDuplicateReview();
    const refreshed = possibleDuplicateReview();
    const refreshedItem = refreshed.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!refreshedItem) throw new Error("remaining fixture item is required");
    refreshedItem.status = "ignored";
    refreshedItem.isTerminal = true;
    refreshedItem.isReviewable = false;
    refreshedItem.lifecycle.allowedActions = ["needs_review"];
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: "import_review_lifecycle_conflict",
              message: "Состояние строки уже изменилось. Обновите данные.",
            },
          }),
          { status: 409 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(refreshed), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderPage(review);

    await user.click(screen.getByRole("button", { name: "Игнорировать" }));
    await user.click(screen.getByRole("button", { name: "Подтвердить" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Обновить строку" }));

    expect(
      await screen.findByRole("button", { name: "Восстановить на проверку" }),
    ).toBeInTheDocument();
  });

  it("confirms an evaluated expense only from the committed response", async () => {
    const user = userEvent.setup();
    const updated = importReviewPayload();
    const item = updated.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.status = "confirmed";
    item.isTerminal = true;
    item.isReviewable = false;
    item.selection.categoryId = expenseCategoryId;
    item.confirmability = { canConfirm: false, blockingReasonCodes: [] };
    item.posting = { operationId: confirmedOperationId, canUndo: true };
    updated.queue.completed = 2;
    updated.queue.remaining = 0;
    updated.queue.firstRemainingItemId = null;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            itemId: remainingItemId,
            classification: { operationType: "expense", source: "explicit" },
            selection: { categoryId: expenseCategoryId, propertyId: null },
            confirmability: { canConfirm: true, blockingReasonCodes: [] },
            ruleSuggestion: {
              isActive: false,
              wasAutoApplied: false,
              ruleId: null,
            },
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            primaryDocumentId: updated.document.id,
            itemId: remainingItemId,
            operationId: confirmedOperationId,
            updatedItemIds: [remainingItemId],
            replayed: false,
            reviews: [updated],
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderPage(importReviewPayload());

    await user.click(screen.getByText("Разобрать строку"));
    await user.selectOptions(
      screen.getByLabelText("Категория"),
      expenseCategoryId,
    );
    await user.click(screen.getByRole("button", { name: "Проверить выбор" }));
    const confirm = await screen.findByRole("button", {
      name: "Подтвердить и провести",
    });
    expect(screen.getByText("Проверено как уникальное")).toBeInTheDocument();
    await user.click(
      screen.getByLabelText("Запомнить как правило для похожих строк"),
    );
    await user.type(
      screen.getByLabelText("Шаблон правила, необязательно"),
      "Магазин",
    );
    await user.click(confirm);

    expect(
      await screen.findByRole("heading", { name: "Все строки обработаны" }),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls[1]?.[1]).toEqual(
      expect.objectContaining({
        headers: expect.objectContaining({
          "Idempotency-Key": expect.any(String),
        }),
        body: JSON.stringify({
          operationType: "expense",
          categoryId: expenseCategoryId,
          propertyId: null,
          expectedStatus: "matched",
          rememberRule: true,
          rulePattern: "Магазин",
        }),
      }),
    );
  });

  it("requires explicit confirmation before undoing a posted operation", async () => {
    const user = userEvent.setup();
    const updated = importReviewPayload();
    const item = updated.items.find(
      (candidate) => candidate.id === completedItemId,
    );
    if (!item) throw new Error("completed fixture item is required");
    item.status = "normalized";
    item.isTerminal = false;
    item.isReviewable = true;
    item.posting = { operationId: null, canUndo: false };
    updated.queue.completed = 0;
    updated.queue.remaining = 2;
    updated.queue.firstRemainingItemId = completedItemId;
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            primaryDocumentId: updated.document.id,
            itemId: completedItemId,
            operationId: confirmedOperationId,
            updatedItemIds: [completedItemId],
            replayed: false,
            reviews: [updated],
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage(importReviewPayload());

    await user.click(
      screen.getByRole("button", { name: "Отменить проведение" }),
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Оставить проведённой" }),
    ).toHaveFocus();
    await user.click(
      screen.getByRole("button", { name: "Отменить проведение" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Осталось 2 из 2" }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/items/${completedItemId}/undo-posting`),
      expect.objectContaining({
        body: JSON.stringify({ expectedOperationId: confirmedOperationId }),
      }),
    );
  });
});

function possibleDuplicateReview() {
  const review = importReviewPayload();
  const item = review.items.find(
    (candidate) => candidate.id === remainingItemId,
  );
  if (!item) throw new Error("remaining fixture item is required");
  item.status = "possible_duplicate";
  item.lifecycle.allowedActions = [
    "mark_unique",
    "mark_duplicate",
    "needs_review",
    "ignore",
  ];
  return review;
}

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
