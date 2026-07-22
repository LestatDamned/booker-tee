import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportReviewPage } from "./import-review-page";
import {
  completedItemId,
  confirmedOperationId,
  expenseCategoryId,
  importReviewPayload,
  propertyId,
  remainingItemId,
} from "./test-support";

describe("import review page", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("renders queue progress and links to the first remaining row", () => {
    renderPage(importReviewPayload());

    expect(
      screen.getByRole("heading", { name: "1 из 2 разобрано" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "1");
    expect(
      screen.getByRole("link", { name: "Следующая нерешённая строка" }),
    ).toHaveAttribute("href", `#raw-${remainingItemId}`);
    expect(
      screen.getByRole("heading", { name: "Проверка выписки" }),
    ).toBeInTheDocument();
    expect(screen.getByText("statement.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText("Требуют решения")).toHaveTextContent("1");
    expect(document.getElementById(`raw-${remainingItemId}`)).not.toBeNull();
    expect(screen.getByText("Проверено как уникальное")).toBeInTheDocument();
  });

  it("shows raw source values without replacing normalized facts", () => {
    renderPage(importReviewPayload());

    expect(
      screen.getAllByText(/Сверить с исходной строкой · данные нормализованы/),
    ).toHaveLength(1);
    expect(screen.getAllByText("После парсера").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-1250,50")).toHaveLength(1);
    expect(screen.getAllByText("*1234")).toHaveLength(1);
  });

  it("renders typed validation totals and a problem on the stable row anchor", () => {
    renderPage(importReviewPayload());

    expect(
      screen.getByRole("heading", { name: "Есть необъяснённая разница" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Поступления" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Списания" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("На начало")).not.toBeInTheDocument();
    expect(screen.queryByText("На конец")).not.toBeInTheDocument();
    expect(
      screen.getByText(/несоответствий: 1; проверено переходов: 1/),
    ).toBeInTheDocument();
    const row = document.getElementById(`raw-${remainingItemId}`);
    expect(row).toHaveTextContent("После строки 1 ожидался остаток");
    expect(row).toHaveTextContent("10 050,50 RUB");
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
      screen.getByRole("heading", {
        name: "Недостаточно данных для сверки",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Сверить с исходной строкой/)).toHaveLength(1);
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
        name: "Разница объяснена",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Исключено: 50,50 RUB из списаний."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Есть необъяснённая разница"),
    ).not.toBeInTheDocument();
  });

  it("shows committed operation facts separately from a stale rule suggestion", () => {
    const review = importReviewPayload();
    const item = review.items[0];
    if (!item) throw new Error("completed fixture item is required");
    item.classification = { operationType: "transfer", source: "explicit" };
    item.selection = { categoryId: null, propertyId: null };
    item.ruleSuggestion = {
      isActive: true,
      wasAutoApplied: false,
      ruleId: null,
      ruleName: "Ошибочное правило",
      pattern: "Покупка",
      operationType: "income",
      categoryId: expenseCategoryId,
      propertyId: null,
    };

    renderPage(review);

    const row = document.getElementById(`raw-${completedItemId}`);
    if (!row) throw new Error("completed row is required");
    expect(within(row).getByText("Перевод")).toBeInTheDocument();
    expect(within(row).queryByText("Без категории")).not.toBeInTheDocument();
    expect(within(row).getByText("Предложено правилом")).toBeInTheDocument();
    expect(
      within(row).queryByText(/Предложено правилом «Ошибочное правило»/),
    ).not.toBeInTheDocument();
    expect(within(row).getByText("Покупка → Продукты")).toBeInTheDocument();
    expect(within(row).getByText("Перевод")).toHaveAttribute(
      "data-variant",
      "outline",
    );
    expect(within(row).getByText("Проведено")).toHaveAttribute(
      "data-variant",
      "status",
    );
  });

  it("renders category, status, and decision source as distinct row facts", () => {
    renderPage(importReviewPayload());

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    expect(
      within(row)
        .getAllByText("Расход")
        .find((element) => element.getAttribute("data-variant") === "outline"),
    ).toBeInTheDocument();
    expect(
      within(row)
        .getAllByText("Без категории")
        .find((element) => element.getAttribute("data-variant") === "soft"),
    ).toBeInTheDocument();
    expect(within(row).getByText("Проверено как уникальное")).toHaveAttribute(
      "data-variant",
      "status",
    );
    expect(within(row).getByText("Тип определён по сумме")).toBeInTheDocument();
  });

  it("shows the financial outcome before actions", () => {
    const review = importReviewPayload();
    const item = review.items[1];
    if (!item) throw new Error("remaining fixture item is required");
    item.selection = {
      categoryId: expenseCategoryId,
      propertyId: review.references.properties[0]?.id ?? null,
    };
    item.confirmability = { canConfirm: true, blockingReasonCodes: [] };
    item.ruleSuggestion.isActive = true;
    item.ruleSuggestion.wasAutoApplied = true;

    renderPage(review);

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    const outcome = within(row).getByRole("region", {
      name: "Итог операции",
    });
    expect(outcome).toHaveTextContent("Будет создан расход");
    expect(outcome).toHaveTextContent("1 250,50 RUB");
    expect(outcome).not.toHaveTextContent("−1 250,50 RUB");
    expect(outcome).toHaveTextContent("Категория: Продукты");
    expect(outcome).toHaveTextContent("Объект: Квартира");
    expect(outcome).toHaveAttribute("data-tone", "expense");
    expect(
      outcome.compareDocumentPosition(
        within(row).getByRole("button", { name: "Подтвердить" }),
      ),
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("shows the created operation outcome for a confirmed row", () => {
    const review = importReviewPayload();
    const item = review.items[0];
    if (!item) throw new Error("completed fixture item is required");
    item.selection.categoryId = expenseCategoryId;

    renderPage(review);

    const row = document.getElementById(`raw-${completedItemId}`);
    if (!row) throw new Error("completed row is required");
    const outcome = within(row).getByRole("region", {
      name: "Итог операции",
    });
    expect(outcome).toHaveTextContent("Создан расход");
    expect(outcome).toHaveTextContent("1 250,50 RUB");
    expect(outcome).toHaveTextContent("Категория: Продукты");
  });

  it("shows an explicit incomplete transfer route", () => {
    const review = importReviewPayload();
    const item = review.items[1];
    if (!item) throw new Error("remaining fixture item is required");
    item.classification = { operationType: "transfer", source: "explicit" };
    item.selection = { categoryId: null, propertyId: null };

    renderPage(review);

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    const outcome = within(row).getByRole("region", {
      name: "Итог операции",
    });
    expect(outcome).toHaveTextContent("Будет создан перевод");
    expect(outcome).toHaveTextContent(
      "Основной счёт → Не выбран счёт назначения",
    );
    expect(outcome).toHaveTextContent("1 250,50 RUB");
    expect(outcome).toHaveAttribute("data-tone", "transfer");
  });

  it("keeps the outcome visible without offering actions in readonly mode", () => {
    const review = importReviewPayload();
    review.capabilities = {
      canWrite: false,
      readonlyReasonCode: "financial_write_forbidden",
    };

    renderPage(review);

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    expect(
      within(row).getByRole("region", { name: "Итог операции" }),
    ).toHaveTextContent("Будет создан расход");
    expect(within(row).queryByRole("button")).not.toBeInTheDocument();
  });

  it.each([
    ["extracted", "Требует решения", "neutral"],
    ["normalized", "Требует решения", "neutral"],
    ["suggested", "Есть предложение", "neutral"],
    ["needs_review", "Нужна проверка", "warning"],
    ["matched", "Проверено как уникальное", "neutral"],
    ["ignored", "Исключено", "neutral"],
    ["duplicate", "Дубль", "danger"],
    ["possible_duplicate", "Возможный дубль", "warning"],
    ["failed", "Ошибка", "danger"],
    ["confirmed", "Проведено", "success"],
  ] as const)(
    "presents the %s status as %s with the %s tone",
    (status, label, tone) => {
      const review = importReviewPayload();
      const item = review.items[1];
      if (!item) throw new Error("remaining fixture item is required");
      item.status = status;

      renderPage(review);

      const row = document.getElementById(`raw-${remainingItemId}`);
      if (!row) throw new Error("remaining row is required");
      const statusBadge = within(row).getByText(label);
      expect(statusBadge).toHaveAttribute("data-variant", "status");
      expect(statusBadge).toHaveAttribute("data-tone", tone);
    },
  );

  it("omits an unknown decision source instead of showing diagnostics", () => {
    const review = importReviewPayload();
    const item = review.items[1];
    if (!item) throw new Error("remaining fixture item is required");
    item.classification.source = "unknown";

    renderPage(review);

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    expect(
      within(row).queryByText("Источник решения не определён"),
    ).not.toBeInTheDocument();
    expect(
      within(row)
        .getAllByText("Расход")
        .find((element) => element.getAttribute("data-variant") === "outline"),
    ).toBeInTheDocument();
    expect(
      within(row)
        .getAllByText("Без категории")
        .find((element) => element.getAttribute("data-tone") === "category"),
    ).toBeInTheDocument();
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
      screen.queryByRole("link", { name: "Следующая нерешённая строка" }),
    ).not.toBeInTheDocument();
  });

  it("explains readonly access", () => {
    const review = importReviewPayload();
    review.capabilities = {
      canWrite: false,
      readonlyReasonCode: "financial_write_forbidden",
    };

    renderPage(review);

    expect(screen.getByText(/только для чтения/)).toBeInTheDocument();
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
      ruleName: "Маркетплейсы",
      pattern: "Покупка",
      operationType: "expense",
      categoryId: expenseCategoryId,
      propertyId: null,
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
    expect(screen.getByText("Предложено правилом")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/apply-rules"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("confirms an auto-applied rule suggestion directly from the row", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const suggestedItem = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!suggestedItem) throw new Error("remaining fixture item is required");
    suggestedItem.selection.categoryId = expenseCategoryId;
    suggestedItem.confirmability = {
      canConfirm: true,
      blockingReasonCodes: [],
    };
    suggestedItem.ruleSuggestion = {
      isActive: true,
      wasAutoApplied: true,
      ruleId: "a6f780bd-fc27-448e-aa66-9f20c478fb4f",
      ruleName: "Маркетплейсы",
      pattern: "Покупка",
      operationType: "expense",
      categoryId: expenseCategoryId,
      propertyId: null,
    };
    const updated = importReviewPayload();
    const updatedItem = updated.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!updatedItem) throw new Error("remaining fixture item is required");
    updatedItem.status = "confirmed";
    updatedItem.isTerminal = true;
    updatedItem.isReviewable = false;
    updatedItem.posting = {
      operationId: confirmedOperationId,
      canUndo: true,
    };
    const fetchMock = vi.fn(() =>
      Promise.resolve(
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
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage(review);

    expect(
      screen.getByRole("button", { name: "Изменить" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Подтвердить" }));

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/items/${remainingItemId}/confirm`),
      expect.objectContaining({
        body: JSON.stringify({
          operationType: "expense",
          categoryId: expenseCategoryId,
          propertyId: null,
          expectedStatus: "matched",
          rememberRule: false,
          rulePattern: null,
        }),
      }),
    );
  });

  it("requires the user to enter the rule matching text", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.selection.categoryId = expenseCategoryId;
    item.confirmability = { canConfirm: true, blockingReasonCodes: [] };
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage(review);

    await user.click(
      screen.getByRole("button", { name: "Проверить и провести" }),
    );
    await user.click(
      screen.getByLabelText("Создать правило для похожих строк"),
    );
    await user.click(
      screen.getByRole("button", { name: "Подтвердить и провести" }),
    );

    const pattern = screen.getByLabelText("Текст для определения *");
    expect(pattern).toHaveFocus();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Укажите текст, по которому определять похожие строки.",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps the local row draft after a network error and panel toggle", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline"))),
    );
    renderPage(importReviewPayload());

    const reviewButton = screen.getByRole("button", {
      name: "Выбрать категорию",
    });
    await user.click(reviewButton);
    const category = screen.getByLabelText("Категория");
    await user.selectOptions(category, expenseCategoryId);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Backend недоступен",
    );
    await user.click(reviewButton);
    await user.click(reviewButton);
    expect(screen.getByLabelText("Категория")).toHaveValue(expenseCategoryId);
  });

  it("keeps categorization and transfer drafts while switching financial meaning", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline"))),
    );
    renderPage(importReviewPayload());

    const reviewButton = screen.getByRole("button", {
      name: "Выбрать категорию",
    });
    await user.click(reviewButton);
    await user.selectOptions(
      screen.getByLabelText("Категория"),
      expenseCategoryId,
    );
    await user.selectOptions(screen.getByLabelText("Объект"), propertyId);

    await user.click(screen.getByRole("radio", { name: "Перевод" }));
    const transferSelection = screen.getByLabelText(
      "Второй счёт или готовая пара",
    );
    await user.selectOptions(
      transferSelection,
      "account:c145935c-67c6-4bf6-a0ce-64e5d611cf47",
    );
    expect(
      screen.getByText("Основной счёт → Накопительный счёт"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Расход" }));
    expect(screen.getByLabelText("Категория")).toHaveValue(expenseCategoryId);
    expect(screen.getByLabelText("Объект")).toHaveValue(propertyId);

    await user.click(screen.getByRole("radio", { name: "Перевод" }));
    expect(screen.getByLabelText("Второй счёт или готовая пара")).toHaveValue(
      "account:c145935c-67c6-4bf6-a0ce-64e5d611cf47",
    );
    await user.click(reviewButton);
    await user.click(reviewButton);
    expect(screen.getByRole("radio", { name: "Перевод" })).toBeChecked();
  });

  it("switches the financial meaning radio group from the keyboard", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline"))),
    );
    renderPage(importReviewPayload());

    await user.click(screen.getByRole("button", { name: "Выбрать категорию" }));
    const ordinary = screen.getByRole("radio", { name: "Расход" });
    ordinary.focus();
    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("radio", { name: "Перевод" })).toBeChecked();
    expect(
      screen.getByLabelText("Второй счёт или готовая пара"),
    ).toBeInTheDocument();
  });

  it("opens a server-classified transfer in the transfer mode", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.classification = { operationType: "transfer", source: "suggested" };

    renderPage(review);
    await user.click(screen.getByRole("button", { name: "Проверить перевод" }));

    expect(screen.getByRole("radio", { name: "Перевод" })).toBeChecked();
    expect(
      screen.getByLabelText("Второй счёт или готовая пара"),
    ).toBeInTheDocument();
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

    await user.click(screen.getByRole("button", { name: "Выбрать категорию" }));
    await user.click(screen.getByRole("button", { name: "Создать категорию" }));
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

    await user.click(screen.getByRole("button", { name: "Выбрать категорию" }));
    await user.click(screen.getByRole("radio", { name: "Перевод" }));
    expect(
      screen.getByText("Основной счёт → Не выбран второй счёт"),
    ).toBeInTheDocument();
    await user.selectOptions(
      screen.getByLabelText("Второй счёт или готовая пара"),
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

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    await user.click(within(row).getByText("Ещё действия"));
    await user.click(
      within(row).getByRole("button", { name: "Отметить дублем" }),
    );
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

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    await user.click(within(row).getByText("Ещё действия"));
    await user.click(within(row).getByRole("button", { name: "Игнорировать" }));
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
              ruleName: null,
              pattern: null,
              operationType: null,
              categoryId: null,
              propertyId: null,
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

    await user.click(screen.getByRole("button", { name: "Выбрать категорию" }));
    await user.selectOptions(
      screen.getByLabelText("Категория"),
      expenseCategoryId,
    );
    const confirm = await screen.findByRole("button", {
      name: "Подтвердить и провести",
    });
    expect(screen.getByText("Проверено как уникальное")).toBeInTheDocument();
    await user.click(
      screen.getByLabelText("Создать правило для похожих строк"),
    );
    await user.type(
      screen.getByLabelText("Текст для определения *"),
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
      await screen.findByRole("heading", { name: "0 из 2 разобрано" }),
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
