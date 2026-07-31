import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  commitImportMapping,
  previewImportMapping,
} from "./api/import-mapping-api";
import { ImportMappingPage } from "./import-mapping-page";
import {
  importMappingPayload,
  importMappingPreview,
  mappingSession,
} from "./test-support";

vi.mock("./api/import-mapping-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/import-mapping-api")>();
  return {
    ...actual,
    commitImportMapping: vi.fn(),
    previewImportMapping: vi.fn(),
  };
});

const previewMock = vi.mocked(previewImportMapping);
const commitMock = vi.mocked(commitImportMapping);
const navigateMock = vi.fn();

vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return { ...actual, useNavigate: () => navigateMock };
});

describe("ImportMappingPage", () => {
  beforeEach(() => {
    previewMock.mockReset();
    commitMock.mockReset();
    navigateMock.mockReset();
  });

  it("shows account context, roles above source columns and the raw table", () => {
    renderPage();

    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(
      screen.getByRole("region", { name: "Настройка импорта" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Основной счёт" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Роль колонки 1, Дата" }),
    ).toHaveValue("operationDateColumn");
    expect(
      screen.getByRole("combobox", {
        name: "Роль колонки 2, Назначение платежа",
      }),
    ).toHaveValue("descriptionColumn");
    expect(screen.getByLabelText("Если у суммы нет знака *")).toHaveValue(
      "require_sign",
    );
    expect(screen.getByLabelText("Исходная таблица")).toHaveValue(
      "Страница 1 · таблица 1 — 3 строки, 4 колонки",
    );
    expect(screen.getByText("Оплата продуктов в магазине")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Показать предпросмотр" }),
    ).toBeInTheDocument();
  });

  it("keeps an independent suggested draft when switching source tables", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByLabelText("Исходная таблица"));
    await user.keyboard("{ArrowDown}{Enter}");

    expect(screen.getByText("Оплата связи")).toBeVisible();
    expect(
      screen.getByRole("radio", {
        name: "Две колонки: списание и поступление",
      }),
    ).toBeChecked();
    expect(
      screen.getByRole("combobox", { name: "Роль колонки 3, Расход" }),
    ).toHaveValue("debitAmountColumn");
    expect(
      screen.getByRole("combobox", { name: "Роль колонки 4, Приход" }),
    ).toHaveValue("creditAmountColumn");
  });

  it("shows a server preview and marks it stale after a draft change", async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue({
      status: "success",
      preview: importMappingPreview(),
    });
    renderPage();

    await user.click(
      screen.getByRole("button", { name: "Показать предпросмотр" }),
    );

    expect(
      await screen.findByText(
        "Списание средств по длинному назначению платежа, которое важно показать полностью",
      ),
    ).toBeVisible();
    expect(screen.getByLabelText(/1.*250,50 RUB/)).toBeVisible();
    expect(screen.getByText("2 из 2 строк корректны")).toBeInTheDocument();

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Роль колонки 4, Остаток" }),
      "descriptionColumn",
    );

    expect(screen.getByText("Нужно обновить")).toBeInTheDocument();
    expect(screen.getByText(/предыдущему предпросмотру/)).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Роль колонки 4, Остаток" }),
    ).toHaveValue("descriptionColumn");
    expect(
      screen.getByRole("combobox", {
        name: "Роль колонки 2, Назначение платежа",
      }),
    ).toHaveValue("balanceAfterColumn");
  });

  it("sends the chosen meaning of an unsigned amount to preview", async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue({
      status: "success",
      preview: importMappingPreview(),
    });
    renderPage();

    await user.selectOptions(
      screen.getByLabelText("Если у суммы нет знака *"),
      "expense",
    );
    await user.click(
      screen.getByRole("button", { name: "Показать предпросмотр" }),
    );

    expect(previewMock).toHaveBeenCalledWith(
      expect.objectContaining({
        command: expect.objectContaining({
          unsignedAmountDirection: "expense",
        }),
      }),
    );
  });

  it("selects a control balance cell and sends its source coordinates", async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue({
      status: "success",
      preview: importMappingPreview(),
    });
    renderPage();

    await user.click(
      screen.getAllByRole("button", { name: "Выбрать в таблице" })[0]!,
    );
    expect(screen.getByText(/Выбираем начальный остаток/)).toBeVisible();
    await user.click(
      screen.getByRole("button", {
        name: /строка 2, колонка 4, значение 10000,00/,
      }),
    );
    expect(screen.getByText(/стр\. 1 · строка 2 · колонка 4/)).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Показать предпросмотр" }),
    );

    expect(previewMock).toHaveBeenCalledWith(
      expect.objectContaining({
        command: expect.objectContaining({
          openingBalanceCell: {
            tableRef: { pageNumber: 1, tableIndex: 0 },
            rowNumber: 2,
            columnIndex: 3,
          },
        }),
      }),
    );
  });

  it("shows an explicit balance-chain mismatch in preview", async () => {
    const user = userEvent.setup();
    const preview = importMappingPreview();
    previewMock.mockResolvedValue({
      status: "success",
      preview: {
        ...preview,
        controlTotals: [
          {
            kind: "opening_balance",
            cell: {
              tableRef: { pageNumber: 1, tableIndex: 0 },
              rowNumber: 2,
              columnIndex: 3,
            },
            rawValue: "10 000,00",
            amount: "10000.00",
            currency: "RUB",
          },
          {
            kind: "closing_balance",
            cell: {
              tableRef: { pageNumber: 1, tableIndex: 0 },
              rowNumber: 3,
              columnIndex: 3,
            },
            rawValue: "12 000,00",
            amount: "12000.00",
            currency: "RUB",
          },
        ],
        reconciliation: {
          openingBalance: "10000.00",
          movement: "1500.00",
          calculatedClosingBalance: "11500.00",
          statementClosingBalance: "12000.00",
          difference: "-500.00",
          matches: false,
        },
      },
    });
    renderPage();

    await user.click(
      screen.getByRole("button", { name: "Показать предпросмотр" }),
    );

    expect(await screen.findByText("Есть расхождение")).toBeVisible();
    expect(screen.getByText("Баланс на начало выписки")).toBeVisible();
    expect(screen.getByText("Изменение баланса по операциям")).toBeVisible();
    expect(screen.getByText("Баланс на конец по расчёту")).toBeVisible();
    expect(screen.getByText("Баланс на конец выписки")).toBeVisible();
    expect(screen.getByText(/Расхождение.*500,00/)).toBeVisible();
  });

  it("links unsigned amount errors to the setting without claiming success", async () => {
    const user = userEvent.setup();
    const preview = importMappingPreview();
    const previewRow = preview.rows[0];
    if (!previewRow) throw new Error("Expected a preview row fixture.");
    previewMock.mockResolvedValue({
      status: "success",
      preview: {
        ...preview,
        rows: [
          {
            ...previewRow,
            amount: null,
            amountRaw: "2 245,77 ₽",
            status: "error",
            errorCodes: ["unsigned_amount_direction_required"],
          },
        ],
        totalRowCount: 79,
        validRowCount: 9,
        invalidRowCount: 70,
        warnings: [
          {
            code: "unsigned_amount_direction_required",
            severity: "warning",
            fields: ["unsignedAmountDirection"],
            affectedRowCount: 70,
          },
          {
            code: "high_error_rate",
            severity: "warning",
            fields: [],
            affectedRowCount: null,
          },
        ],
        canImport: true,
      },
    });
    renderPage();

    await user.click(
      screen.getByRole("button", { name: "Показать предпросмотр" }),
    );

    const status = await screen.findByText("70 строк требуют исправления");
    expect(status).toBeVisible();
    expect(status).toHaveAttribute("data-tone", "danger");
    expect(screen.queryByText("Можно продолжать")).not.toBeInTheDocument();
    const amount = screen.getByLabelText(/2.*245,77 RUB/);
    expect(amount).toBeVisible();
    expect(amount).not.toHaveAccessibleName(/₽/);

    const direction = screen.getByLabelText("Если у суммы нет знака *");
    expect(direction).toHaveAttribute("aria-invalid", "true");
    expect(
      screen.getByText(
        "В 70 строках сумма указана без знака. Выберите поступление или списание.",
      ),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Изменить правило" }));
    expect(direction).toHaveFocus();

    await user.selectOptions(direction, "expense");
    expect(direction).toHaveAttribute("aria-invalid", "false");
    expect(screen.getByText("Нужно обновить")).toBeVisible();
  });

  it("preserves the draft and explains server validation errors", async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue({
      status: "validation_error",
      message: "Схема не прошла проверку.",
      fieldErrors: {
        firstDataRowNumber: ["Первая строка должна содержать данные."],
      },
    });
    renderPage();
    const rowInput = screen.getByLabelText(
      "С какой строки начинаются операции *",
    );

    await user.clear(rowInput);
    await user.type(rowInput, "3");
    await user.click(
      screen.getByRole("button", { name: "Показать предпросмотр" }),
    );

    expect(
      await screen.findByText("Схема не прошла проверку."),
    ).toBeInTheDocument();
    expect(rowInput).toHaveValue(3);
    expect(
      screen.getByText("Первая строка должна содержать данные."),
    ).toBeInTheDocument();
  });

  it("imports once, optionally saves a template and opens review", async () => {
    const user = userEvent.setup();
    const preview = importMappingPreview();
    previewMock.mockResolvedValue({ status: "success", preview });
    let resolveImport:
      | ((value: Awaited<ReturnType<typeof commitImportMapping>>) => void)
      | undefined;
    commitMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveImport = resolve;
        }),
    );
    renderPage();

    await user.click(
      screen.getByRole("button", { name: "Показать предпросмотр" }),
    );
    await screen.findByRole("button", {
      name: `Импортировать ${preview.totalRowCount} строк`,
    });
    await user.click(screen.getByLabelText("Сохранить как шаблон"));
    await user.type(
      screen.getByLabelText("Название шаблона *"),
      "Экспобанк — карта",
    );
    const importButton = screen.getByRole("button", {
      name: `Импортировать ${preview.totalRowCount} строк`,
    });
    await user.click(importButton);
    await user.click(importButton);

    expect(commitMock).toHaveBeenCalledTimes(1);
    expect(commitMock).toHaveBeenCalledWith(
      expect.objectContaining({
        templateName: "Экспобанк — карта",
        idempotencyKey: expect.any(String),
      }),
    );
    expect(
      screen.getByRole("button", { name: "Создаём строки…" }),
    ).toBeDisabled();

    await act(async () => {
      resolveImport?.({
        status: "success",
        result: {
          documentId: importMappingPayload().documentId,
          status: "requires_review",
          importedRowCount: preview.totalRowCount,
          templateId: null,
          replayed: false,
          reviewTarget: {
            kind: "import_review",
            documentId: importMappingPayload().documentId,
          },
        },
      });
    });

    expect(navigateMock).toHaveBeenCalledWith(
      `/imports/documents/${importMappingPayload().documentId}/review`,
    );
  });

  it("does not offer import for a stale preview", async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue({
      status: "success",
      preview: importMappingPreview(),
    });
    renderPage();

    await user.click(
      screen.getByRole("button", { name: "Показать предпросмотр" }),
    );
    expect(
      await screen.findByRole("button", { name: /Импортировать/ }),
    ).toBeVisible();
    await user.selectOptions(
      screen.getByLabelText("Если у суммы нет знака *"),
      "expense",
    );

    expect(
      screen.queryByRole("button", { name: /Импортировать/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Обновить предпросмотр" }),
    ).toBeVisible();
  });

  it("explains a server-owned capability block", () => {
    const mapping = importMappingPayload();
    renderPage({
      ...mapping,
      capability: {
        allowed: false,
        blockingReasonCodes: ["confirmed_rows_exist"],
      },
    });

    expect(
      screen.getByRole("heading", { name: "Строки уже проведены" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Показать предпросмотр" }),
    ).not.toBeInTheDocument();
  });
});

function renderPage(mapping = importMappingPayload()) {
  return render(
    <MemoryRouter>
      <ImportMappingPage mapping={mapping} session={mappingSession} />
    </MemoryRouter>,
  );
}
