import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActionStack } from "./action-stack/action-stack";
import { Badge } from "./badge/badge";
import { Button } from "./button/button";
import { IconButton } from "./button/icon-button";
import { ExpansionPanel } from "./expansion-panel/expansion-panel";
import { Field } from "./field/field";
import { Fieldset } from "./field/fieldset";
import { FormErrorSummary } from "./field/form-error-summary";
import { MoneyValue } from "./money-value/money-value";
import { RequestState } from "./request-state/request-state";
import { WorkbenchRow } from "./workbench-row/workbench-row";

describe("foundation controls", () => {
  it("makes a loading button unavailable and announces its state", () => {
    render(<Button isLoading>Сохранить</Button>);

    const button = screen.getByRole("button", { name: "Сохранить" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("keeps reversible cancellation visually quieter than deletion", () => {
    render(
      <>
        <Button tone="dangerSecondary">Отменить операцию</Button>
        <Button tone="danger">Удалить окончательно</Button>
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Отменить операцию" }),
    ).toHaveAttribute("data-tone", "dangerSecondary");
    expect(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    ).toHaveAttribute("data-tone", "danger");
  });

  it("requires an accessible label for an icon-only action", () => {
    render(<IconButton aria-label="Редактировать" icon="edit" />);

    expect(
      screen.getByRole("button", { name: "Редактировать" }),
    ).toBeInTheDocument();
  });

  it("connects a field label and validation error to its native control", () => {
    render(
      <Field
        error="Обязательное поле"
        errorId="description-error"
        htmlFor="description"
        label="Описание"
      >
        <input
          aria-describedby="description-error"
          aria-invalid="true"
          id="description"
        />
      </Field>,
    );

    expect(screen.getByLabelText("Описание")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByText("Обязательное поле")).toHaveAttribute(
      "id",
      "description-error",
    );
  });

  it("groups a short choice set and links summary errors to fields", () => {
    render(
      <>
        <FormErrorSummary
          errors={[
            {
              fieldId: "operation-expense",
              label: "Тип операции",
              message: "Выберите тип.",
            },
          ]}
          message="Проверьте данные."
        />
        <Fieldset legend="Тип операции" required>
          <label htmlFor="operation-expense">
            <input id="operation-expense" name="type" type="radio" />
            Расход
          </label>
        </Fieldset>
      </>,
    );

    expect(
      screen.getByRole("group", { name: "Тип операции" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Тип операции: Выберите тип." }),
    ).toHaveAttribute("href", "#operation-expense");
  });
});

describe("financial presentation primitives", () => {
  it("renders a server-formatted amount without recalculating it", () => {
    render(<MoneyValue amount="−4 890,50" currency="RUB" tone="expense" />);

    expect(screen.getByText("−4 890,50")).toBeInTheDocument();
    expect(screen.getByText("RUB")).toBeInTheDocument();
  });

  it("renders status text independently of its visual tone", () => {
    render(<Badge tone="warning">требует проверки</Badge>);
    expect(screen.getByText("требует проверки")).toBeInTheDocument();
  });
});

describe("request and workbench composition", () => {
  it("announces an error and exposes retry", () => {
    const retry = vi.fn();
    render(
      <RequestState
        message="Backend недоступен"
        onRetry={retry}
        status="error"
        title="Ошибка загрузки"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Backend недоступен");
    expect(retry).toHaveBeenCalledOnce();
  });

  it("closes an expansion through its accessible icon action", () => {
    const close = vi.fn();
    render(
      <ExpansionPanel
        id="edit-panel"
        isOpen
        onClose={close}
        title="Редактирование"
      >
        Форма
      </ExpansionPanel>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Закрыть панель" }));
    expect(close).toHaveBeenCalledOnce();
  });

  it("composes row content and grouped dangerous actions", () => {
    render(
      <WorkbenchRow
        aside={
          <ActionStack
            danger={<Button tone="danger">Отменить операцию</Button>}
            primary={<Button>Редактировать</Button>}
          />
        }
        date="2026-07-20"
        description="Аренда за июль"
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Аренда за июль" }),
    ).toBeInTheDocument();
    expect(screen.getByText("20.07.2026")).toHaveAttribute(
      "datetime",
      "2026-07-20",
    );
    fireEvent.click(screen.getByText("Ещё действия"));
    expect(screen.getByLabelText("Опасные действия")).toBeInTheDocument();
  });

  it.each([
    ["recent", "Недавно"],
    ["target", "Текущая строка"],
    ["working", "В работе"],
  ] as const)(
    "shows the %s row state without relying on color",
    (state, label) => {
      render(<WorkbenchRow description="Операция" state={state} />);

      expect(screen.getByText(label)).toBeVisible();
    },
  );
});
