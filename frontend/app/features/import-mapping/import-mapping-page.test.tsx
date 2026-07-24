import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { previewImportMapping } from "./api/import-mapping-api";
import { ImportMappingPage } from "./import-mapping-page";
import {
  importMappingPayload,
  importMappingPreview,
  mappingSession,
} from "./test-support";

vi.mock("./api/import-mapping-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/import-mapping-api")>();
  return { ...actual, previewImportMapping: vi.fn() };
});

const previewMock = vi.mocked(previewImportMapping);

describe("ImportMappingPage", () => {
  beforeEach(() => {
    previewMock.mockReset();
  });

  it("shows account context, roles above source columns and the raw table", () => {
    renderPage();

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
