import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { directory, ruleId, session } from "./test-support";
import { TransactionRulesPage } from "./transaction-rules-page";

describe("TransactionRulesPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders a compact rule summary twice with contextual edit controls", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: "Правила операций" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Все правила: 3" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Вкл.")).toBeVisible();
    expect(screen.getByText("Выкл.")).toBeVisible();
    expect(screen.getAllByText("OZON → Маркетплейсы")).toHaveLength(2);
    expect(screen.getAllByText("Описание содержит «OZON»")).toHaveLength(2);
    expect(screen.getAllByText("Сумма: 100.00–500.00")).toHaveLength(2);
    expect(screen.getAllByText("Маркетплейсы")).toHaveLength(2);
    expect(screen.getAllByText("Объект: Старая квартира · архив")).toHaveLength(
      2,
    );
    expect(screen.getAllByText("Предложений: 4")).toHaveLength(2);
    expect(
      screen.getByText(/Сохранённые предложения не меняются автоматически/),
    ).toBeVisible();
    expect(
      screen.queryByText("Влияет на финансовый результат"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Сопоставляет только будущие review-операции"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Любая абсолютная сумма"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Любой счёт")).not.toBeInTheDocument();
    expect(screen.getAllByText("Приоритет 20")).toHaveLength(2);
    const editActions = screen.getAllByRole("button", { name: "Изменить" });
    expect(editActions).toHaveLength(2);
    editActions.forEach((action) =>
      expect(action).toHaveTextContent("Изменить"),
    );
    editActions.forEach((action) =>
      expect(action).toHaveAttribute("data-tone", "secondary"),
    );
    expect(
      screen.queryByRole("button", { name: "Выключить" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Ещё действия" }),
    ).toHaveLength(2);
  });

  it("omits default constraints and names auto apply as prefill", () => {
    const compactRule = {
      ...directory.items[0]!,
      priority: 100,
      condition: {
        ...directory.items[0]!.condition,
        account: null,
        amountMin: null,
        amountMax: null,
      },
      outcome: {
        ...directory.items[0]!.outcome,
        applicationMode: "auto_apply" as const,
        property: null,
        autoDescription: null,
      },
      usage: { directRawSuggestionCount: 0 },
    };

    renderPage("/rules", { ...directory, items: [compactRule] });

    expect(screen.getAllByText("Предзаполнение")).toHaveLength(2);
    expect(screen.queryByText("Приоритет 100")).not.toBeInTheDocument();
    expect(screen.queryByText(/Сумма:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Счёт:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Объект:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Предложений:/)).not.toBeInTheDocument();
  });

  it("opens the category filter and navigates with URL-owned state", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Фильтры" }));
    const category = screen.getByRole("combobox", {
      name: "Категория результата",
    });
    await user.click(category);
    expect(
      screen.getByRole("option", {
        name: "Архивная категория · архив",
      }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("option", { name: "Архивная категория · архив" }),
    );
    await user.click(screen.getByRole("button", { name: "Применить" }));

    expect(screen.getByTestId("location")).toHaveTextContent(
      `?category_id=${directory.references.categories[1]!.id}`,
    );
  });

  it("marks a deep-linked rule and reports a missing target", () => {
    const { unmount } = renderPage(`/rules#rule-${ruleId}`);
    expect(document.querySelectorAll('[data-targeted="true"]')).toHaveLength(2);
    unmount();

    renderPage("/rules#rule-11111111-1111-4111-8111-111111111111");
    expect(
      screen.getByText("Правило не найдено в текущей выборке"),
    ).toBeVisible();
  });

  it("renders a deep-linked rule outside the current page", () => {
    const target = {
      ...directory.items[0]!,
      id: "11111111-1111-4111-8111-111111111111",
      name: "Целевое правило",
    };

    renderPage(`/rules?rule_id=${target.id}#rule-${target.id}`, {
      ...directory,
      targetItem: target,
    });

    expect(screen.getAllByText("Целевое правило")).toHaveLength(2);
    expect(document.querySelectorAll('[data-targeted="true"]')).toHaveLength(2);
  });

  it("shows explicit viewer read-only copy and no controls", () => {
    renderPage("/rules", {
      ...directory,
      capabilities: {
        canCreate: false,
        canSeedDefaults: false,
        readonlyReasonCode: "financial_write_forbidden",
      },
      items: directory.items.map((item) => ({
        ...item,
        capabilities: {
          ...item.capabilities,
          canUpdate: false,
          canDisable: false,
        },
      })),
    });

    expect(
      screen.getByText(/Просматривать смысл правил можно с вашей ролью/),
    ).toBeVisible();
    expect(screen.queryByText("Редактировать")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Новое правило" }),
    ).not.toBeInTheDocument();
  });

  it("creates a rule from the right-side dialog and preserves review semantics", async () => {
    const user = userEvent.setup();
    const created = {
      ...directory.items[0]!,
      id: "fc2d7025-7789-4312-9191-d9731d4be611",
      name: "Такси",
      condition: { ...directory.items[0]!.condition, pattern: "YANDEX GO" },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ item: created, replayed: false }), {
            headers: { "Content-Type": "application/json" },
            status: 201,
          }),
        ),
      ),
    );
    renderPage();

    await user.click(screen.getByRole("button", { name: "Новое правило" }));
    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.getByText(/не подтверждает операцию/i)).toBeVisible();
    await user.type(screen.getByLabelText(/^Условие/), "YANDEX GO");
    await user.selectOptions(screen.getByLabelText("Тип операции"), "expense");
    await user.click(screen.getByRole("button", { name: "Создать правило" }));

    expect(await screen.findByText("Правило «Такси» создано.")).toBeVisible();
    expect(screen.getAllByText("Такси")).toHaveLength(2);
    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        `#rule-${created.id}`,
      ),
    );
  });

  it("confirms discarding a dirty create draft", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Новое правило" }));
    await user.type(screen.getByLabelText(/^Условие/), "OZON");
    await user.click(screen.getByRole("button", { name: "Отмена" }));
    expect(
      screen.getByRole("heading", { name: "Закрыть создание правила?" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Продолжить создание" }),
    );
    expect(screen.getByDisplayValue("OZON")).toBeVisible();
  });

  it("edits one rule under its desktop row and replaces the committed row without changing URL state", async () => {
    const user = userEvent.setup();
    const committed = {
      ...directory.items[0]!,
      name: "OZON покупки",
      updatedAt: "2026-08-02T10:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            item: directory.items[0],
            references: directory.references,
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(committed), {
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderPage("/rules?q=ozon&page=1");

    const edit = screen.getAllByRole("button", { name: "Изменить" })[0]!;
    await user.click(edit);
    expect(edit).toHaveAttribute("aria-expanded", "true");
    const form = await screen.findByRole("heading", {
      name: "Изменить правило",
    });
    const panel = form.closest("section")!;
    expect(
      within(panel).getByText(
        /Описание содержит «OZON» → Расход · Маркетплейсы.*Предложение\. Подтверждение — в Import Review\./,
      ),
    ).toBeVisible();
    expect(
      panel.querySelector("[data-transaction-rule-preview]"),
    ).toBeInTheDocument();
    await user.click(within(panel).getByLabelText("Объект"));
    expect(
      screen.getByRole("option", { name: "Старая квартира · архив" }),
    ).toBeVisible();
    await user.keyboard("{Escape}");
    const name = within(panel).getByLabelText("Название");
    await user.clear(name);
    await user.type(name, "OZON покупки");
    await user.click(within(panel).getByRole("button", { name: "Сохранить" }));

    expect(
      await screen.findByText("Правило «OZON покупки» сохранено."),
    ).toBeVisible();
    expect(screen.getAllByText("OZON покупки")).toHaveLength(2);
    expect(screen.getByTestId("location")).toHaveTextContent("?q=ozon");
    const updateInit = fetchMock.mock.calls[1]![1] as RequestInit;
    expect(JSON.parse(String(updateInit.body))).toMatchObject({
      expectedUpdatedAt: "2026-08-02T09:00:00Z",
      propertyId: directory.items[0]!.outcome.property!.id,
    });
  });

  it("keeps the draft on a stale update until the user explicitly reloads", async () => {
    const user = userEvent.setup();
    const latest = {
      ...directory.items[0]!,
      name: "Версия из другого окна",
      updatedAt: "2026-08-02T10:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              item: directory.items[0],
              references: directory.references,
            }),
            { headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              error: {
                code: "transaction_rule_update_conflict",
                message: "Правило уже изменилось в другом окне.",
              },
            }),
            { headers: { "Content-Type": "application/json" }, status: 409 },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ item: latest, references: directory.references }),
            { headers: { "Content-Type": "application/json" } },
          ),
        ),
    );
    renderPage();
    await user.click(screen.getAllByRole("button", { name: "Изменить" })[0]!);
    const name = await screen.findByDisplayValue("OZON → Маркетплейсы");
    await user.clear(name);
    await user.type(name, "Мой черновик");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(
      await screen.findByText(
        "Ваш черновик сохранён. Загрузка актуальной версии заменит его только после нажатия кнопки.",
      ),
    ).toBeVisible();
    expect(screen.getByDisplayValue("Мой черновик")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Загрузить актуальную версию" }),
    );
    expect(
      await screen.findByDisplayValue("Версия из другого окна"),
    ).toBeVisible();
  });

  it("keeps only one inline editor and confirms a dirty switch", async () => {
    const user = userEvent.setup();
    const second = {
      ...directory.items[0]!,
      id: "9b6bb65d-ec08-4528-bfcb-81466e00ce29",
      name: "Такси",
      condition: { ...directory.items[0]!.condition, pattern: "TAXI" },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              item: directory.items[0],
              references: directory.references,
            }),
            { headers: { "Content-Type": "application/json" } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ item: second, references: directory.references }),
            { headers: { "Content-Type": "application/json" } },
          ),
        ),
    );
    renderPage("/rules", {
      ...directory,
      items: [directory.items[0]!, second],
    });
    const buttons = screen.getAllByRole("button", { name: "Изменить" });
    await user.click(buttons[0]!);
    const name = await screen.findByDisplayValue("OZON → Маркетплейсы");
    await user.type(name, " draft");
    await user.click(buttons[1]!);
    expect(
      screen.getByRole("heading", { name: "Отбросить изменения правила?" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Отбросить изменения" }),
    );
    expect(await screen.findByDisplayValue("Такси")).toBeVisible();
    expect(
      screen.getAllByRole("heading", { name: "Изменить правило" }),
    ).toHaveLength(1);
  });

  it("seeds only after confirmation and reports truthful counts", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              createdRules: 2,
              existingRules: 51,
              createdCategories: 1,
            }),
            { headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );
    renderPage();
    await user.click(screen.getByRole("button", { name: "Базовые правила" }));
    expect(
      screen.getByText(/Существующие правила, режимы и состояния не изменятся/),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Добавить недостающие" }),
    );
    expect(
      await screen.findByText(/создано 2, уже было 51, новых категорий 1/),
    ).toBeVisible();
  });

  it("disables future matching, preserves existing suggestions and keeps list state", async () => {
    const user = userEvent.setup();
    const changed = {
      ...directory.items[0]!,
      isActive: false,
      updatedAt: "2026-08-02T10:00:00Z",
      capabilities: {
        ...directory.items[0]!.capabilities,
        canDisable: false,
        canEnable: true,
        deleteBlockedReasonCode: "raw_suggestions" as const,
      },
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          item: changed,
          impact: {
            futureMatchingChanged: true,
            existingSuggestionsChanged: false,
            existingSuggestionCount: 4,
          },
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage("/rules?q=ozon");

    const actionsTrigger = screen.getAllByRole("button", {
      name: "Ещё действия",
    })[0]!;
    await user.click(actionsTrigger);
    await user.click(screen.getAllByRole("button", { name: "Выключить" })[0]!);
    expect(
      await screen.findByText(
        /Новые операции больше не сопоставляются; 4 существующих предложений сохранено/,
      ),
    ).toBeVisible();
    expect(screen.getAllByText("Выключено")).toHaveLength(2);
    expect(actionsTrigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByTestId("location")).toHaveTextContent("?q=ozon");
    const body = JSON.parse(
      String((fetchMock.mock.calls[0]![1] as RequestInit).body),
    );
    expect(body).toEqual({
      expectedActive: true,
      expectedUpdatedAt: "2026-08-02T09:00:00Z",
    });
  });

  it("reloads an authoritative lifecycle conflict and explicitly retries", async () => {
    const user = userEvent.setup();
    const fresh = { ...directory.items[0]!, updatedAt: "2026-08-02T09:30:00Z" };
    const changed = {
      ...fresh,
      isActive: false,
      updatedAt: "2026-08-02T10:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: "transaction_rule_lifecycle_conflict",
              message: "Правило уже изменилось.",
            },
          }),
          { headers: { "Content-Type": "application/json" }, status: 409 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ item: fresh, references: directory.references }),
          { headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            item: changed,
            impact: {
              futureMatchingChanged: true,
              existingSuggestionsChanged: false,
              existingSuggestionCount: 4,
            },
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    await user.click(screen.getAllByRole("button", { name: "Выключить" })[0]!);
    expect(await screen.findByText("Правило уже изменилось.")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Обновить и повторить" }),
    );
    expect(
      await screen.findByText(/Правило «OZON → Маркетплейсы» выключено/),
    ).toBeVisible();
    expect(
      JSON.parse(String((fetchMock.mock.calls[2]![1] as RequestInit).body)),
    ).toMatchObject({ expectedUpdatedAt: "2026-08-02T09:30:00Z" });
  });

  it("removes a disabled rule from the active URL view and updates counts", async () => {
    const user = userEvent.setup();
    const activeDirectory = {
      ...directory,
      appliedFilters: {
        ...directory.appliedFilters,
        status: "active" as const,
      },
      page: { ...directory.page, total: 1 },
    };
    const changed = {
      ...directory.items[0]!,
      isActive: false,
      updatedAt: "2026-08-02T10:00:00Z",
      capabilities: {
        ...directory.items[0]!.capabilities,
        canDisable: false,
        canEnable: true,
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              item: changed,
              impact: {
                futureMatchingChanged: true,
                existingSuggestionsChanged: false,
                existingSuggestionCount: 4,
              },
            }),
            { headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );
    renderPage("/rules?status=active", activeDirectory);
    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    await user.click(screen.getAllByRole("button", { name: "Выключить" })[0]!);
    expect(await screen.findByText("Правил пока нет")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Активные правила: 1" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Выключенные правила: 2" }),
    ).toBeVisible();
  });

  it("explains why a rule with an archived target cannot be enabled", async () => {
    const blocked = {
      ...directory.items[0]!,
      isActive: false,
      capabilities: {
        ...directory.items[0]!.capabilities,
        canDisable: false,
        canEnable: false,
        enableBlockedReasonCode: "property_archived" as const,
      },
    };
    const user = userEvent.setup();
    renderPage("/rules", { ...directory, items: [blocked] });
    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    await user.click(
      screen.getAllByRole("button", { name: "Почему нельзя включить" })[0]!,
    );
    expect(screen.getByText("Правило пока нельзя включить")).toBeVisible();
    expect(
      screen.getByText(
        "Сначала выберите активный объект или уберите объект из правила.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Изменить правило" }),
    ).toBeVisible();
  });

  it("keeps delete in dangerous overflow, focuses cancel and removes only the rule", async () => {
    const user = userEvent.setup();
    const deletable = {
      ...directory.items[0]!,
      isActive: false,
      usage: { directRawSuggestionCount: 0 },
      capabilities: {
        ...directory.items[0]!.capabilities,
        canDisable: false,
        canEnable: true,
        canDelete: true,
        deleteBlockedReasonCode: null,
      },
    };
    const snapshot = {
      ...directory,
      items: [deletable],
      counts: { all: 3, active: 2, disabled: 1 },
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ deletedId: deletable.id, name: deletable.name }),
          { headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderPage("/rules?status=disabled", snapshot);

    expect(
      screen.queryByRole("button", { name: "Удалить правило" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    const deleteAction = screen.getByRole("button", {
      name: "Удалить правило",
    });
    expect(
      deleteAction.closest('[aria-label="Опасные действия"]'),
    ).not.toBeNull();
    await user.click(deleteAction);
    expect(screen.getByText(/без возможности восстановления/)).toBeVisible();
    expect(screen.getByText(/источники импорта.*не изменятся/)).toBeVisible();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Отмена" })).toHaveFocus(),
    );
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Удалить правило",
      }),
    );

    expect(
      await screen.findByText(/Финансовые данные не изменены/),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Все правила: 2" })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Выключенные правила: 0" }),
    ).toBeVisible();
    expect(screen.queryByText("OZON → Маркетплейсы")).not.toBeInTheDocument();
    const body = JSON.parse(
      String((fetchMock.mock.calls[0]![1] as RequestInit).body),
    );
    expect(body).toEqual({
      expectedActive: false,
      expectedUpdatedAt: "2026-08-02T09:00:00Z",
    });
  });

  it("explains preserved provenance instead of offering a false delete action", async () => {
    const user = userEvent.setup();
    const referenced = {
      ...directory.items[0]!,
      isActive: false,
      capabilities: {
        ...directory.items[0]!.capabilities,
        canDisable: false,
        canEnable: true,
        canDelete: false,
        deleteBlockedReasonCode: "raw_suggestions" as const,
      },
    };
    renderPage("/rules", { ...directory, items: [referenced] });

    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    expect(
      screen.queryByRole("button", { name: "Удалить правило" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Почему нельзя удалить" }),
    );
    expect(screen.getByText("Правило нельзя удалить")).toBeVisible();
    expect(
      screen.getByText(/4 review-предложений хранит provenance/),
    ).toBeVisible();
  });

  it("reloads an authoritative delete conflict before explicit retry", async () => {
    const user = userEvent.setup();
    const deletable = {
      ...directory.items[0]!,
      isActive: false,
      usage: { directRawSuggestionCount: 0 },
      capabilities: {
        ...directory.items[0]!.capabilities,
        canDisable: false,
        canDelete: true,
        deleteBlockedReasonCode: null,
      },
    };
    const fresh = { ...deletable, updatedAt: "2026-08-02T09:30:00Z" };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: "transaction_rule_delete_conflict",
              message: "Правило уже изменилось в другом окне.",
            },
          }),
          { headers: { "Content-Type": "application/json" }, status: 409 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ item: fresh, references: directory.references }),
          { headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ deletedId: fresh.id, name: fresh.name }),
          { headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderPage("/rules", { ...directory, items: [deletable] });

    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    await user.click(screen.getByRole("button", { name: "Удалить правило" }));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Удалить правило",
      }),
    );
    expect(await screen.findByText("Правило изменилось")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Обновить и повторить" }),
    );

    expect(
      await screen.findByText(/Финансовые данные не изменены/),
    ).toBeVisible();
    expect(
      JSON.parse(String((fetchMock.mock.calls[2]![1] as RequestInit).body)),
    ).toMatchObject({ expectedUpdatedAt: "2026-08-02T09:30:00Z" });
  });

  it("normalizes the last page after delete while preserving filters", async () => {
    const user = userEvent.setup();
    const deletable = {
      ...directory.items[0]!,
      isActive: false,
      usage: { directRawSuggestionCount: 0 },
      capabilities: {
        ...directory.items[0]!.capabilities,
        canDisable: false,
        canDelete: true,
        deleteBlockedReasonCode: null,
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({ deletedId: deletable.id, name: deletable.name }),
            { headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );
    renderPage("/rules?q=ozon&status=disabled&page=2&page_size=25", {
      ...directory,
      items: [deletable],
      page: {
        page: 2,
        pageSize: 25,
        total: 26,
        totalPages: 2,
        hasPrevious: true,
        hasNext: false,
      },
      appliedFilters: { q: "ozon", categoryId: null, status: "disabled" },
    });
    await user.click(
      screen.getAllByRole("button", { name: "Ещё действия" })[0]!,
    );
    await user.click(screen.getByRole("button", { name: "Удалить правило" }));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Удалить правило",
      }),
    );

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        "?q=ozon&status=disabled&page_size=25",
      ),
    );
  });
});

function renderPage(initialEntry = "/rules", snapshot = directory) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <TransactionRulesPage directory={snapshot} session={session} />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.search}
      {location.hash}
    </output>
  );
}
