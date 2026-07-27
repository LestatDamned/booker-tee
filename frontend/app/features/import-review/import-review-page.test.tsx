import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
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
  it("renders queue progress and unresolved-row navigation", () => {
    renderPage(importReviewPayload());

    expect(
      screen.getByRole("heading", { name: "1 из 2 разобрано" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "1");
    expect(
      screen.getByRole("button", { name: "Предыдущая нерешённая строка" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Следующая нерешённая строка" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("heading", { name: "Проверка выписки" }),
    ).toBeInTheDocument();
    expect(screen.getByText("statement.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText("Требуют решения")).toHaveTextContent("1");
    expect(document.getElementById(`raw-${remainingItemId}`)).not.toBeNull();
    expect(screen.getByText("Проверено как уникальное")).toBeInTheDocument();
  });

  it("opens all rows first and preserves filter counts and pressed state", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const remainingItem = review.items.find(
      (item) => item.id === remainingItemId,
    );
    if (!remainingItem) throw new Error("remaining fixture item is required");
    remainingItem.ruleSuggestion.isActive = true;
    renderPage(review);

    const pending = screen.getByRole("button", {
      name: "Требуют решения 1",
    });
    const suggestions = screen.getByRole("button", {
      name: "Предложения 1",
    });
    const problems = screen.getByRole("button", { name: "Проблемы 1" });
    const complete = screen.getByRole("button", { name: "Завершённые 1" });
    const all = screen.getByRole("button", { name: "Все 2" });

    expect(all).toHaveAttribute("aria-pressed", "true");
    expect(pending).toHaveAttribute("aria-pressed", "false");
    expect(document.getElementById(`raw-${remainingItemId}`)).not.toBeNull();
    expect(document.getElementById(`raw-${completedItemId}`)).not.toBeNull();

    for (const filter of [pending, suggestions, problems, complete, all]) {
      await user.click(filter);
      expect(filter).toHaveAttribute("aria-pressed", "true");
    }

    await user.click(complete);
    expect(document.getElementById(`raw-${completedItemId}`)).not.toBeNull();
    expect(document.getElementById(`raw-${remainingItemId}`)).toBeNull();
    await user.click(all);
    expect(document.getElementById(`raw-${completedItemId}`)).not.toBeNull();
    expect(document.getElementById(`raw-${remainingItemId}`)).not.toBeNull();
  });

  it("keeps imports active and stores the review filter in the URL", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    renderPage(
      review,
      `/imports/documents/${review.document.id}/review?from=imports&filter=complete`,
    );

    for (const importsLink of screen.getAllByRole("link", {
      name: "Импорты",
    })) {
      expect(importsLink).toHaveAttribute("href", "/imports");
      expect(importsLink).toHaveAttribute("aria-current", "page");
    }
    expect(
      screen.getByRole("button", { name: "Завершённые 1" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(document.getElementById(`raw-${completedItemId}`)).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "Проблемы 1" }));
    let currentSearch = new URLSearchParams(
      screen.getByTestId("current-search").textContent ?? "",
    );
    expect(currentSearch.get("from")).toBe("imports");
    expect(currentSearch.get("filter")).toBe("problems");

    await user.click(screen.getByRole("button", { name: "Требуют решения 1" }));
    currentSearch = new URLSearchParams(
      screen.getByTestId("current-search").textContent ?? "",
    );
    expect(currentSearch.get("from")).toBe("imports");
    expect(currentSearch.get("filter")).toBe("pending");

    await user.click(screen.getByRole("button", { name: "Все 2" }));
    currentSearch = new URLSearchParams(
      screen.getByTestId("current-search").textContent ?? "",
    );
    expect(currentSearch.get("from")).toBe("imports");
    expect(currentSearch.has("filter")).toBe(false);
  });

  it.each([
    ["pending", "Требуют решения 0", "Нет строк, требующих решения"],
    ["suggestions", "Предложения 0", "Нет предложений"],
    ["problems", "Проблемы 0", "Нет проблемных строк"],
    ["complete", "Завершённые 0", "Нет завершённых строк"],
  ] as const)(
    "shows focused empty copy for the %s filter",
    async (filter, buttonName, emptyTitle) => {
      const user = userEvent.setup();
      const review = importReviewPayload();
      if (filter === "pending") {
        review.items = review.items.filter((item) => item.isTerminal);
      }
      if (filter === "problems" && review.validation) {
        review.validation.rowProblems = [];
      }
      if (filter === "complete") {
        review.items.forEach((item) => {
          item.isTerminal = false;
        });
      }
      renderPage(review, filter === "pending" ? "/?filter=pending" : "/");

      const filterButton = screen.getByRole("button", { name: buttonName });
      if (filter !== "pending") await user.click(filterButton);

      expect(filterButton).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByText(emptyTitle)).toBeInTheDocument();
    },
  );

  it("keeps internal row identity out of the ordinary review copy", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.rowIndex = 0;
    renderPage(review, "/?filter=pending");

    expect(screen.queryByText("Разобрать строку 0")).not.toBeInTheDocument();
    expect(screen.getByText("*1234")).not.toBeVisible();
    expect(screen.getAllByText("Основной счёт")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Выбрать категорию" }));
    expect(
      screen.getByRole("heading", { name: "Операция" }),
    ).toBeInTheDocument();
    const panel = document.getElementById(`review-panel-${remainingItemId}`);
    if (!panel) throw new Error("review panel is required");
    expect(
      within(panel).queryByText("Что мешает подтверждению:"),
    ).not.toBeInTheDocument();
    expect(
      within(panel).queryByText("Для дохода или расхода выберите категорию."),
    ).not.toBeInTheDocument();
  });

  it("keeps operation context and the optional auto-rule visible", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.selection.categoryId = expenseCategoryId;
    item.confirmability = { canConfirm: true, blockingReasonCodes: [] };
    renderPage(review, "/?filter=pending");

    await user.click(
      screen.getByRole("button", { name: "Проверить операцию" }),
    );

    const context = screen.getByLabelText("Контекст текущей операции");
    expect(context).toHaveTextContent("Текущая операция");
    expect(context).toHaveTextContent("20.07.2026");
    expect(context).toHaveTextContent("Покупка в магазине");
    expect(context).toHaveTextContent("−1 250,50");

    const decision = screen.getByLabelText("Решение по операции");
    expect(
      within(decision).getByRole("textbox", { name: /Автоправило/ }),
    ).toBeVisible();
    expect(within(decision).queryByLabelText("Итог операции")).toBeNull();
    const cancel = within(decision).getByRole("button", { name: "Отмена" });
    const confirm = within(decision).getByRole("button", { name: "Провести" });
    expect(confirm).toBeVisible();
    expect(cancel.compareDocumentPosition(confirm)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(
      screen.getByRole("button", { name: "Ещё действия" }),
    ).toHaveAttribute("aria-expanded", "false");
  });

  it("shows raw source values from the secondary technical action", async () => {
    const user = userEvent.setup();
    renderPage(importReviewPayload());

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    expect(within(row).queryByText(/По карте \*1234/)).not.toBeInTheDocument();
    await user.click(within(row).getByText("Ещё действия"));
    const sourceAction = screen.getByRole("button", {
      name: "Исходные данные",
    });
    expect(sourceAction).toHaveAttribute("aria-expanded", "false");
    await user.click(sourceAction);

    expect(
      within(row).getByRole("heading", { name: "Исходные данные строки 2" }),
    ).toBeInTheDocument();
    expect(within(row).getByText("Данные нормализованы")).toBeInTheDocument();
    expect(within(row).getAllByText("После обработки").length).toBeGreaterThan(
      0,
    );
    expect(within(row).getByText("-1250,50")).toBeInTheDocument();
    expect(within(row).getByText("*1234")).toBeInTheDocument();
  });

  it("shows reconciliation formulas before technical details", async () => {
    const user = userEvent.setup();
    renderPage(importReviewPayload());

    expect(
      screen.getByRole("heading", {
        name: "Остаток после операции не сходится",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Сверка итогов")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Поступления" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Списания" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("table", { name: "Контрольные суммы выписки" }),
    ).toBeInTheDocument();
    expect(screen.getByText("По распознанным строкам")).toBeInTheDocument();
    expect(screen.getByText("Исключённые строки")).toBeInTheDocument();
    expect(screen.getByText("Итог в выписке")).toBeInTheDocument();
    expect(screen.getByText("Разница")).toBeInTheDocument();
    expect(screen.queryByText("Подробнее о сверке")).not.toBeInTheDocument();
    expect(screen.queryByText("На начало")).not.toBeInTheDocument();
    expect(screen.queryByText("На конец")).not.toBeInTheDocument();

    const technicalSummary = screen.getByText("Технические данные");
    const technicalDetails = technicalSummary.closest("details");
    expect(technicalDetails).not.toHaveAttribute("open");
    await user.click(technicalSummary);
    expect(technicalDetails).toHaveAttribute("open");
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
    expect(
      screen.getAllByRole("button", { name: "Ещё действия" }),
    ).toHaveLength(2);
  });

  it("distinguishes a mismatch explained by ignored rows", () => {
    const review = importReviewPayload();
    if (!review.validation) throw new Error("validation fixture is required");
    review.validation.reasonCode = "ignored_rows_explain_mismatch";
    review.validation.calculatedTotalInflow = "54807.89";
    review.validation.calculatedTotalOutflow = "71768.09";
    review.validation.ignoredTotalInflow = "50000.00";
    review.validation.ignoredTotalOutflow = "50000.00";
    review.validation.statementTotalInflow = "104807.89";
    review.validation.statementTotalOutflow = "121768.09";
    review.validation.unexplainedInflowDifference = "0.00";
    review.validation.unexplainedOutflowDifference = "0.00";
    review.validation.rowProblems = [];

    renderPage(review);

    expect(
      screen.getByRole("heading", {
        name: "Разница объяснена",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("50 000,00 RUB исключено из поступлений и списаний."),
    ).toBeInTheDocument();
    const inflow = screen
      .getByRole("heading", { name: "Поступления" })
      .closest("tr");
    const outflow = screen
      .getByRole("heading", { name: "Списания" })
      .closest("tr");
    expect(inflow).toHaveTextContent("54 807,89");
    expect(inflow).toHaveTextContent("50 000,00");
    expect(inflow).toHaveTextContent("104 807,89");
    expect(inflow).toHaveTextContent("0,00");
    expect(outflow).toHaveTextContent("71 768,09");
    expect(outflow).toHaveTextContent("121 768,09");
    expect(
      screen.queryByText("Есть необъяснённая разница"),
    ).not.toBeInTheDocument();
  });

  it("shows committed operation facts separately from a stale rule suggestion", async () => {
    const user = userEvent.setup();
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

    await user.click(screen.getByRole("button", { name: "Завершённые 1" }));

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
    const workflowStatus = within(row)
      .getAllByText("Проведено")
      .find((element) => element.getAttribute("data-tone") === "success");
    expect(workflowStatus).toBeInTheDocument();
    expect(workflowStatus).not.toHaveAttribute("data-variant");
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
    expect(
      within(row).getByText("Проверено как уникальное"),
    ).not.toHaveAttribute("data-variant");
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
    expect(outcome).toHaveTextContent("Готово к проведению");
    expect(outcome).toHaveTextContent("Расход → Продукты");
    expect(outcome).not.toHaveTextContent("1 250,50 RUB");
    expect(outcome).toHaveTextContent("Объект: Квартира");
    expect(outcome).toHaveAttribute("data-state", "pending");
    expect(outcome).toHaveAttribute("data-tone", "expense");
    expect(within(row).getAllByLabelText(/1.250,50 RUB/)).toHaveLength(1);
    expect(
      outcome.compareDocumentPosition(
        within(row).getByRole("button", { name: "Подтвердить" }),
      ),
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("shows the created operation outcome for a confirmed row", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items[0];
    if (!item) throw new Error("completed fixture item is required");
    item.selection.categoryId = expenseCategoryId;

    renderPage(review);

    await user.click(screen.getByRole("button", { name: "Завершённые 1" }));

    const row = document.getElementById(`raw-${completedItemId}`);
    if (!row) throw new Error("completed row is required");
    const outcome = within(row).getByRole("region", {
      name: "Итог операции",
    });
    expect(outcome).toHaveTextContent("Проведено");
    expect(outcome).toHaveTextContent("Расход → Продукты");
    expect(outcome).not.toHaveTextContent("1 250,50 RUB");
    expect(outcome).toHaveAttribute("data-state", "confirmed");
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
    expect(outcome).toHaveTextContent("Предварительный результат");
    expect(outcome).toHaveTextContent(
      "Основной счёт → Не выбран счёт назначения",
    );
    expect(outcome).not.toHaveTextContent("1 250,50 RUB");
    expect(outcome).toHaveAttribute("data-state", "incomplete");
    expect(outcome).toHaveAttribute("data-tone", "transfer");
  });

  it("shows both persisted account names for a confirmed transfer", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items[0];
    if (!item) throw new Error("completed fixture item is required");
    item.classification = { operationType: "transfer", source: "explicit" };
    item.selection = { categoryId: null, propertyId: null };
    item.transfer.counterpartyAccount = {
      id: "c145935c-67c6-4bf6-a0ce-64e5d611cf47",
      name: "Накопительный счёт",
      currency: "RUB",
    };

    renderPage(review);

    await user.click(screen.getByRole("button", { name: "Завершённые 1" }));

    const row = document.getElementById(`raw-${completedItemId}`);
    if (!row) throw new Error("completed row is required");
    const outcome = within(row).getByRole("region", {
      name: "Итог операции",
    });
    expect(outcome).toHaveTextContent("Проведено");
    expect(outcome).toHaveTextContent("Основной счёт → Накопительный счёт");
    expect(outcome).not.toHaveTextContent("Счёт перевода");
  });

  it("keeps the outcome visible without offering write actions in readonly mode", async () => {
    const user = userEvent.setup();
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
    ).toHaveTextContent("Предварительный результат");
    expect(
      within(row).queryByRole("button", { name: "Подтвердить" }),
    ).not.toBeInTheDocument();
    expect(
      within(row).queryByRole("button", { name: "Изменить операцию" }),
    ).not.toBeInTheDocument();
    await user.click(within(row).getByRole("button", { name: "Ещё действия" }));
    expect(
      screen.getByRole("button", { name: "Исходные данные" }),
    ).toBeInTheDocument();
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
      const workflowStatus = within(row)
        .getAllByText(label)
        .find((element) => element.getAttribute("data-tone") === tone);
      expect(workflowStatus).toBeInTheDocument();
      if (tone === "warning" || tone === "danger") {
        expect(workflowStatus).toHaveAttribute("data-variant", "soft");
      } else {
        expect(workflowStatus).not.toHaveAttribute("data-variant");
      }
      expect(workflowStatus).toHaveAttribute("data-tone", tone);
    },
  );

  it.each([
    ["missing_category", "Выберите категорию"],
    ["missing_amount", "Не определена сумма"],
    ["duplicate_review_required", "Проверьте возможный дубль"],
    ["transfer_accounts_required", "Выберите второй счёт перевода"],
  ] as const)(
    "shows the %s blocking reason before opening the editor",
    (reasonCode, reasonLabel) => {
      const review = importReviewPayload();
      const item = review.items[1];
      if (!item) throw new Error("remaining fixture item is required");
      item.confirmability = {
        canConfirm: false,
        blockingReasonCodes: [reasonCode],
      };

      renderPage(review);

      const row = document.getElementById(`raw-${remainingItemId}`);
      if (!row) throw new Error("remaining row is required");
      const blocker = within(row).getByLabelText("Что мешает подтверждению");
      expect(blocker).toHaveTextContent(reasonLabel);
      expect(
        blocker.compareDocumentPosition(
          within(row).getByRole("region", {
            name: "Итог операции",
          }),
        ),
      ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    },
  );

  it("omits the blocking reason when the server allows confirmation", () => {
    const review = importReviewPayload();
    const item = review.items[1];
    if (!item) throw new Error("remaining fixture item is required");
    item.confirmability = { canConfirm: true, blockingReasonCodes: [] };

    renderPage(review);

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    expect(
      within(row).queryByLabelText("Что мешает подтверждению"),
    ).not.toBeInTheDocument();
  });

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

  it.each([
    ["confirmed", "settled", false],
    ["suggested", "suggestion", false],
    ["needs_review", "review", false],
    ["matched", "problem", true],
  ] as const)(
    "gives a %s row the separate %s workflow treatment",
    async (status, workflowState, withProblem) => {
      const user = userEvent.setup();
      const review = importReviewPayload();
      const item = review.items[1];
      if (!item || !review.validation) {
        throw new Error("remaining review fixture is required");
      }
      item.status = status;
      item.isTerminal = status === "confirmed";
      item.isReviewable = status !== "confirmed";
      item.ruleSuggestion.isActive = status === "suggested";
      if (!withProblem) review.validation.rowProblems = [];

      renderPage(review);

      if (status === "confirmed") {
        await user.click(screen.getByRole("button", { name: "Завершённые 2" }));
      }

      expect(document.getElementById(`raw-${remainingItemId}`)).toHaveAttribute(
        "data-workflow-state",
        workflowState,
      );
    },
  );

  it("uses accessible disclosure semantics for secondary actions", async () => {
    const user = userEvent.setup();
    renderPage(importReviewPayload());
    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    const disclosure = within(row).getByRole("button", {
      name: "Ещё действия",
    });

    disclosure.focus();
    expect(disclosure).toHaveFocus();
    expect(disclosure.tagName).toBe("BUTTON");
    await user.click(disclosure);
    expect(disclosure).toHaveAttribute("aria-expanded", "true");
    const sourceAction = screen.getByRole("button", {
      name: "Исходные данные",
    });
    await user.click(sourceAction);

    expect(
      within(row).getByRole("heading", { name: "Исходные данные строки 2" }),
    ).toBeInTheDocument();
    expect(row).toHaveAttribute("data-state", "working");
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
    expect(
      screen.getByText("Операций для проверки пока нет"),
    ).toBeInTheDocument();
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
      screen.getByRole("button", { name: "Изменить операцию" }),
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

  it("uses the optional pattern to choose whether to create a rule", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.selection.categoryId = expenseCategoryId;
    item.confirmability = { canConfirm: true, blockingReasonCodes: [] };
    renderPage(review);

    await user.click(
      screen.getByRole("button", { name: "Проверить операцию" }),
    );
    const pattern = screen.getByRole("textbox", {
      name: /Автоправило/,
    });
    expect(pattern).toHaveValue("");
    expect(
      screen.getByRole("button", { name: "Провести" }),
    ).toBeInTheDocument();

    await user.type(pattern, "KRASNOE&BELOE");

    expect(
      screen.getByRole("button", { name: "Провести с правилом" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Итог правила")).toHaveTextContent(
      "KRASNOE&BELOE→Расход · Продукты · Без объекта",
    );
  });

  it("does not repeat the raw description in the rule field", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.raw.description =
      "28/06/2026 KRASNOE&BELOE карта 5017 операция 177979632694";
    item.normalized.description = "KRASNOE&BELOE";
    item.selection.categoryId = expenseCategoryId;
    item.confirmability = { canConfirm: true, blockingReasonCodes: [] };
    renderPage(review);

    await user.click(
      screen.getByRole("button", { name: "Проверить операцию" }),
    );

    const posting = screen.getByLabelText("Подтверждение операции");
    expect(
      within(posting).queryByText(
        "28/06/2026 KRASNOE&BELOE карта 5017 операция 177979632694",
      ),
    ).not.toBeInTheDocument();
    const pattern = within(posting).getByRole("textbox", {
      name: /Автоправило/,
    });
    expect(pattern).toHaveValue("");
    await user.type(pattern, "KRASNOE&BELOE");
    expect(within(posting).getByLabelText("Итог правила")).toHaveTextContent(
      "KRASNOE&BELOE→Расход · Продукты · Без объекта",
    );
  });

  it("discards the auto-rule pattern on explicit editor cancel", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.selection.categoryId = expenseCategoryId;
    item.confirmability = { canConfirm: true, blockingReasonCodes: [] };
    renderPage(review);

    const reviewButton = screen.getByRole("button", {
      name: "Проверить операцию",
    });
    await user.click(reviewButton);
    await user.type(
      screen.getByRole("textbox", { name: /Автоправило/ }),
      "KRASNOE&BELOE",
    );
    await user.click(screen.getByRole("button", { name: "Отмена" }));
    await user.click(reviewButton);

    expect(screen.getByRole("textbox", { name: /Автоправило/ })).toHaveValue(
      "",
    );
    expect(
      screen.getByRole("button", { name: "Провести" }),
    ).toBeInTheDocument();
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
    await chooseCategory(user, "Продукты");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Backend недоступен",
    );
    await user.click(reviewButton);
    await user.click(reviewButton);
    expect(screen.getByLabelText("Категория")).toHaveValue("Продукты");
  });

  it("filters categories and supports keyboard selection", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline"))),
    );
    renderPage(importReviewPayload());

    await user.click(screen.getByRole("button", { name: "Выбрать категорию" }));
    const category = screen.getByRole("combobox", { name: "Категория" });
    await user.click(category);
    expect(category).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("listbox").parentElement?.parentElement).toBe(
      document.body,
    );

    await user.type(category, "прод");
    expect(
      screen.getByRole("option", { name: "Продукты" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "Без категории" }),
    ).not.toBeInTheDocument();

    await user.keyboard("{Enter}");
    expect(category).toHaveValue("Продукты");
    expect(category).toHaveAttribute("aria-expanded", "false");
  });

  it("resets the editor to server state on explicit cancel", async () => {
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
    await chooseCategory(user, "Продукты");
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Отмена" }));
    expect(reviewButton).toHaveFocus();
    await user.click(reviewButton);

    expect(screen.getByLabelText("Категория")).toHaveValue(
      "Выберите категорию",
    );
    expect(screen.getByRole("radio", { name: "Расход" })).toBeChecked();
  });

  it("discards the local transfer mode and account on explicit cancel", async () => {
    const user = userEvent.setup();
    renderPage(importReviewPayload());

    const reviewButton = screen.getByRole("button", {
      name: "Выбрать категорию",
    });
    await user.click(reviewButton);
    await user.click(screen.getByRole("radio", { name: "Перевод" }));
    await user.selectOptions(
      screen.getByLabelText("Второй счёт или готовая пара"),
      "account:c145935c-67c6-4bf6-a0ce-64e5d611cf47",
    );

    await user.click(screen.getByRole("button", { name: "Отмена" }));
    await user.click(reviewButton);
    expect(screen.getByRole("radio", { name: "Расход" })).toBeChecked();

    await user.click(screen.getByRole("radio", { name: "Перевод" }));
    expect(screen.getByLabelText("Второй счёт или готовая пара")).toHaveValue(
      "",
    );
  });

  it("uses the active confirm action without a duplicate outcome", async () => {
    const user = userEvent.setup();
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.selection.categoryId = expenseCategoryId;
    item.confirmability = { canConfirm: true, blockingReasonCodes: [] };
    renderPage(review);

    await user.click(
      screen.getByRole("button", { name: "Проверить операцию" }),
    );

    expect(
      screen.queryByText(/Проверки выбора пройдены/),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Провести" })).toBeEnabled();
    const panel = document.getElementById(`review-panel-${remainingItemId}`);
    if (!panel) throw new Error("review panel is required");
    expect(within(panel).queryByLabelText("Итог операции")).toBeNull();
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
    await chooseCategory(user, "Продукты");
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
    expect(screen.getByLabelText("Категория")).toHaveValue("Продукты");
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

  it("keeps category selection primary when an ordinary operation has a transfer candidate", () => {
    const review = importReviewPayload();
    const item = review.items.find(
      (candidate) => candidate.id === remainingItemId,
    );
    if (!item) throw new Error("remaining fixture item is required");
    item.transfer.rawRowCandidates = [
      {
        itemId: "19a27f5a-8de0-4be3-b934-1ce813d2593a",
        documentId: "7f5ff7ba-f79e-4f30-9ee1-b25257dfed67",
        rowIndex: 3,
        operationDate: "2026-07-21",
        description: "Возможная парная операция",
        amount: "1250.50",
        currency: "RUB",
        account: {
          id: "c145935c-67c-4bf6-a0ce-64e5d611cf47",
          name: "Накопительный счёт",
          currency: "RUB",
        },
        dayDistance: 1,
      },
    ];

    renderPage(review);

    expect(
      screen.getByRole("button", { name: "Выбрать категорию" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Проверить перевод" }),
    ).not.toBeInTheDocument();
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
    expect(name).toHaveAttribute("aria-invalid", "true");
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
    const transferPanel = screen.getByLabelText("Параметры перевода");
    const cancel = within(transferPanel).getByRole("button", {
      name: "Отмена",
    });
    const confirm = within(transferPanel).getByRole("button", {
      name: "Провести перевод",
    });
    expect(cancel.compareDocumentPosition(confirm)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    await user.click(confirm);

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
    await user.click(screen.getByRole("button", { name: "Завершённые 2" }));
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

  it("shows server-owned duplicate evidence and both explicit decisions", () => {
    renderPage(possibleDuplicateReview());

    const row = document.getElementById(`raw-${remainingItemId}`);
    if (!row) throw new Error("remaining row is required");
    const comparison = within(row).getByRole("region", {
      name: "Возможный дубль",
    });
    expect(comparison).toHaveTextContent("Совпали: счёт, дата, сумма, валюта.");
    expect(comparison).toHaveTextContent("Текущая строка");
    expect(comparison).toHaveTextContent("Найденный кандидат");
    expect(comparison).toHaveTextContent("Покупка в магазине");
    expect(comparison).toHaveTextContent("Покупка в супермаркете");
    expect(
      within(comparison).getByRole("link", { name: "previous-statement.xlsx" }),
    ).toHaveAttribute(
      "href",
      "/app/imports/documents/2aecac73-98a3-468b-bd75-ac89445f908e",
    );
    expect(
      within(row).getByRole("button", { name: "Это новая операция" }),
    ).toBeInTheDocument();
    expect(
      within(row).getByRole("button", { name: "Отметить дублем" }),
    ).toBeInTheDocument();
    expect(
      within(row).queryByLabelText("Что мешает подтверждению"),
    ).not.toBeInTheDocument();
  });

  it("offers retry after a lifecycle network error", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline"))),
    );
    renderPage(possibleDuplicateReview());

    await user.click(
      screen.getByRole("button", { name: "Это новая операция" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Проверьте соединение и повторите действие",
    );
    expect(
      screen.getByRole("button", { name: "Повторить действие" }),
    ).toBeInTheDocument();
  });

  it("offers authoritative refresh after a lifecycle validation error", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "validation_error",
                message: "Данные строки больше не подходят для этого действия.",
                fieldErrors: {},
              },
            }),
            { status: 422 },
          ),
        ),
      ),
    );
    renderPage(possibleDuplicateReview());

    await user.click(
      screen.getByRole("button", { name: "Это новая операция" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Обновите строку и проверьте данные",
    );
    expect(
      screen.getByRole("button", { name: "Обновить строку" }),
    ).toBeInTheDocument();
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
    await user.click(screen.getByRole("button", { name: "Игнорировать" }));
    await user.click(screen.getByRole("button", { name: "Подтвердить" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Обновить строку" }));
    await user.click(screen.getByRole("button", { name: "Завершённые 2" }));
    const refreshedRow = document.getElementById(`raw-${remainingItemId}`);
    if (!refreshedRow) throw new Error("refreshed row is required");
    await user.click(within(refreshedRow).getByText("Ещё действия"));

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
    await chooseCategory(user, "Продукты");
    const confirm = await screen.findByRole("button", {
      name: "Провести",
    });
    expect(screen.getByText("Проверено как уникальное")).toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", { name: /Автоправило/ }),
      "Магазин",
    );
    await user.click(confirm);

    expect(
      await screen.findByRole("heading", { name: "Все строки обработаны" }),
    ).toBeInTheDocument();
    expect(document.getElementById(`raw-${remainingItemId}`)).toHaveAttribute(
      "data-state",
      "default",
    );
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

    await user.click(screen.getByRole("button", { name: "Завершённые 1" }));
    await user.click(screen.getByRole("button", { name: "Ещё действия" }));

    await user.click(
      screen.getByRole("button", { name: "Вернуть на проверку" }),
    );
    expect(fetchMock).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog", {
      name: "Вернуть операцию на проверку?",
    });
    expect(dialog).toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: "Отмена" }),
    ).toHaveFocus();
    await user.click(
      within(dialog).getByRole("button", { name: "Вернуть на проверку" }),
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
  item.confirmability = {
    canConfirm: false,
    blockingReasonCodes: ["duplicate_review_required"],
  };
  item.duplicateEvidence = {
    reasonCode: "same_account_date_amount_currency",
    matchingFields: ["account", "operation_date", "amount", "currency"],
    candidate: {
      itemId: "32f1f811-6a21-4c9c-a12a-fc1bb72b782d",
      documentId: "2aecac73-98a3-468b-bd75-ac89445f908e",
      documentFilename: "previous-statement.xlsx",
      operationId: null,
      operationDate: "2026-07-20",
      description: "Покупка в супермаркете",
      amount: "-1250.50",
      currency: "RUB",
    },
  };
  return review;
}

function renderPage(
  review: ReturnType<typeof importReviewPayload>,
  route = "/",
) {
  render(
    <MemoryRouter initialEntries={[route]}>
      <ImportReviewPage review={review} session={sessionPayload} />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="current-search">{location.search}</output>;
}

async function chooseCategory(
  user: ReturnType<typeof userEvent.setup>,
  categoryName: string,
) {
  const category = screen.getByRole("combobox", { name: "Категория" });
  await user.click(category);
  await user.type(category, categoryName.slice(0, 4));
  await user.click(screen.getByRole("option", { name: categoryName }));
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
