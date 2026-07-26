import { useState, type FormEventHandler } from "react";

import { Field } from "../../ui/field/field";
import { Fieldset } from "../../ui/field/fieldset";
import { SearchableSelect } from "../../ui/searchable-select/searchable-select";
import type {
  ImportMappingCommand,
  ImportMappingControlTotalCell,
  ImportMappingDto,
  ImportMappingSourceTable,
} from "./api/import-mapping-api";
import {
  mappingAmountMode,
  mappingTableKey,
  suggestedColumn,
  type AmountMode,
  type MappingFieldErrors,
} from "./mapping-draft";
import {
  ControlTotalMapping,
  type ControlTotalKind,
} from "./control-total-mapping";
import styles from "./import-mapping-page.module.css";
import { MappingSourceTable } from "./mapping-source-table";

type MappingFormProps = {
  command: ImportMappingCommand;
  disabled: boolean;
  errors: MappingFieldErrors;
  mapping: ImportMappingDto;
  table: ImportMappingSourceTable;
  tables: ImportMappingSourceTable[];
  onChange: (command: ImportMappingCommand) => void;
  onSelectTable: (tableKey: string) => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
};

export function MappingForm({
  command,
  disabled,
  errors,
  mapping,
  onChange,
  onSelectTable,
  onSubmit,
  table,
  tables,
}: MappingFormProps) {
  const [activeControlTotalKind, setActiveControlTotalKind] =
    useState<ControlTotalKind | null>(null);
  const amountMode = mappingAmountMode(command);
  const update = (patch: Partial<ImportMappingCommand>) =>
    onChange({ ...command, ...patch });

  const changeAmountMode = (mode: AmountMode) => {
    if (mode === "single") {
      update({
        amountColumn: command.amountColumn ?? suggestedColumn(table, "amount"),
        debitAmountColumn: null,
        creditAmountColumn: null,
      });
      return;
    }
    update({
      amountColumn: null,
      debitAmountColumn:
        command.debitAmountColumn ?? suggestedColumn(table, "debit_amount"),
      creditAmountColumn:
        command.creditAmountColumn ?? suggestedColumn(table, "credit_amount"),
    });
  };

  return (
    <form
      className={styles.mappingForm}
      id="mapping-form"
      noValidate
      onSubmit={onSubmit}
    >
      <header className={styles.mappingHeader}>
        <div>
          <span className={styles.sectionLabel}>Настройка</span>
          <h2>Роли колонок</h2>
          <p>
            Назначьте роль непосредственно над каждой колонкой исходной выписки.
          </p>
        </div>
        <div className={styles.tablePicker}>
          <label htmlFor="sourceTable">Исходная таблица</label>
          <SearchableSelect
            disabled={disabled}
            emptyMessage="Таблицы не найдены"
            id="sourceTable"
            options={tables.map((option) => ({
              label: tableTitle(option),
              value: mappingTableKey(option.ref),
            }))}
            placeholder="Найти таблицу по странице"
            value={mappingTableKey(table.ref)}
            onChange={onSelectTable}
          />
        </div>
      </header>

      <div className={styles.globalSettings}>
        <Fieldset
          error={
            errors.amountColumn ??
            errors.debitAmountColumn ??
            errors.creditAmountColumn
          }
          errorId="mapping-amount-error"
          hint="От выбора зависят роли, доступные над колонками таблицы."
          legend="Как в выписке указана сумма"
          required
        >
          <div className={styles.amountModes}>
            <label>
              <input
                checked={amountMode === "single"}
                disabled={disabled}
                name="amountMode"
                type="radio"
                onChange={() => changeAmountMode("single")}
              />
              <span>
                <strong>Одна колонка «Сумма»</strong>
              </span>
            </label>
            <label>
              <input
                checked={amountMode === "split"}
                disabled={disabled}
                name="amountMode"
                type="radio"
                onChange={() => changeAmountMode("split")}
              />
              <span>
                <strong>Две колонки: списание и поступление</strong>
              </span>
            </label>
          </div>
        </Fieldset>

        {amountMode === "single" ? (
          <Field
            error={errors.unsignedAmountDirection}
            errorId="unsigned-amount-direction-error"
            hint="Явные +, − и скобки всегда имеют приоритет."
            htmlFor="unsignedAmountDirection"
            label="Если у суммы нет знака"
            required
          >
            <select
              id="unsignedAmountDirection"
              aria-describedby={
                errors.unsignedAmountDirection
                  ? "unsigned-amount-direction-error"
                  : undefined
              }
              aria-invalid={Boolean(errors.unsignedAmountDirection)}
              disabled={disabled}
              value={command.unsignedAmountDirection}
              onChange={(event) =>
                update({
                  unsignedAmountDirection: event.target
                    .value as ImportMappingCommand["unsignedAmountDirection"],
                })
              }
            >
              <option value="require_sign">Остановить и показать ошибку</option>
              <option value="income">Считать поступлением</option>
              <option value="expense">Считать списанием</option>
            </select>
          </Field>
        ) : (
          <div className={styles.contextNote}>
            <strong>Направление задают колонки</strong>
            <span>
              Роли «Списание» и «Зачисление» определят знак автоматически.
            </span>
          </div>
        )}

        <Field
          error={errors.firstDataRowNumber}
          errorId="first-data-row-error"
          hint="Отмечена линией в исходной таблице."
          htmlFor="firstDataRowNumber"
          label="С какой строки начинаются операции"
          required
        >
          <input
            id="firstDataRowNumber"
            aria-describedby={
              errors.firstDataRowNumber ? "first-data-row-error" : undefined
            }
            aria-invalid={Boolean(errors.firstDataRowNumber)}
            disabled={disabled}
            max={Math.max(table.rowCount, 1)}
            min={1}
            type="number"
            value={command.firstDataRowNumber}
            onChange={(event) =>
              update({ firstDataRowNumber: Number(event.target.value) })
            }
          />
        </Field>

        <Field
          error={errors.defaultCurrency}
          errorId="default-currency-error"
          hint="Если в строке нет отдельной валюты."
          htmlFor="defaultCurrency"
          label="Валюта, если она не указана"
          required
        >
          <input
            id="defaultCurrency"
            aria-describedby={
              errors.defaultCurrency ? "default-currency-error" : undefined
            }
            aria-invalid={Boolean(errors.defaultCurrency)}
            disabled={disabled}
            maxLength={3}
            value={command.defaultCurrency}
            onChange={(event) =>
              update({ defaultCurrency: event.target.value.toUpperCase() })
            }
          />
        </Field>
      </div>

      <ControlTotalMapping
        activeKind={activeControlTotalKind}
        command={command}
        disabled={disabled}
        mapping={mapping}
        onChange={onChange}
        onSelectKind={setActiveControlTotalKind}
      />

      <MappingSourceTable
        command={command}
        disabled={disabled}
        documentId={mapping.documentId}
        errors={errors}
        key={`${table.ref.pageNumber}:${table.ref.tableIndex}`}
        selectionKind={activeControlTotalKind}
        table={table}
        onSelectControlTotal={(cell: ImportMappingControlTotalCell) => {
          onChange({
            ...command,
            [activeControlTotalKind === "opening_balance"
              ? "openingBalanceCell"
              : "closingBalanceCell"]: cell,
          });
          setActiveControlTotalKind(null);
        }}
        onChange={onChange}
      />
    </form>
  );
}

function tableTitle(table: ImportMappingSourceTable): string {
  const source =
    table.sourceType === "text_candidate" ? "блок строк" : "таблица";
  return `Страница ${table.ref.pageNumber} · ${source} ${table.ref.tableIndex + 1} — ${countLabel(table.rowCount, ["строка", "строки", "строк"])}, ${countLabel(table.columnCount, ["колонка", "колонки", "колонок"])}`;
}

function countLabel(
  count: number,
  [one, few, many]: [string, string, string],
): string {
  const lastTwoDigits = Math.abs(count) % 100;
  const lastDigit = lastTwoDigits % 10;
  const form =
    lastTwoDigits >= 11 && lastTwoDigits <= 14
      ? many
      : lastDigit === 1
        ? one
        : lastDigit >= 2 && lastDigit <= 4
          ? few
          : many;
  return `${count} ${form}`;
}
