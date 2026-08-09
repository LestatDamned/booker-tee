import type { DebtCreateRequest, DebtKind } from "./api/debts-api";
import { todayIsoDate } from "../../shared/date/format-date";

export const debtKindLabels: Record<DebtKind, string> = {
  credit_card: "Кредитная карта",
  loan_payable: "Полученный заём",
  loan_receivable: "Выданный заём",
  mortgage: "Ипотека",
};

export const debtStatusLabels = {
  active: "Активен",
  archived: "В архиве",
  no_debt: "Долга нет",
  settled: "Погашен",
} as const;

export type DebtCreateAction = DebtCreateRequest["action"];

export const debtActionLabels: Record<DebtCreateAction, string> = {
  add_existing: "Добавить существующий долг",
  give_loan: "Я выдал заём",
  open_credit_card: "Открыть кредитную карту",
  take_loan: "Я получил заём",
};

export type DebtCreateDraft = {
  action: DebtCreateAction;
  accountId: string;
  amount: string;
  creditLimit: string;
  currency: string;
  description: string;
  kind: DebtKind;
  maturityDate: string;
  name: string;
  notes: string;
  openedOn: string;
  openingBalance: string;
  openingDebt: string;
  operationDate: string;
  originalPrincipal: string;
};

export type DebtCreateField = keyof DebtCreateDraft;
export type DebtCreateFieldErrors = Partial<Record<DebtCreateField, string>>;

export class DebtCreateDrafts {
  static empty(defaultCurrency: string): DebtCreateDraft {
    return {
      action: "add_existing",
      accountId: "",
      amount: "",
      creditLimit: "",
      currency: defaultCurrency,
      description: "",
      kind: "loan_payable",
      maturityDate: "",
      name: "",
      notes: "",
      openedOn: "",
      openingBalance: "",
      openingDebt: "0.00",
      operationDate: todayIsoDate(),
      originalPrincipal: "",
    };
  }

  static validate(draft: DebtCreateDraft): DebtCreateFieldErrors {
    const errors: DebtCreateFieldErrors = {};
    if (!draft.name.trim()) errors.name = "Введите название долга.";
    if (!/^[A-Za-z]{3}$/.test(draft.currency.trim())) {
      errors.currency = "Введите трёхбуквенный код валюты.";
    }
    if (draft.maturityDate && draft.openedOn > draft.maturityDate) {
      errors.maturityDate = "Конечный срок не может быть раньше даты открытия.";
    }
    if (draft.action === "add_existing") {
      requirePositive(draft.openingBalance, "openingBalance", errors);
      requirePositive(draft.originalPrincipal, "originalPrincipal", errors);
    } else if (draft.action === "open_credit_card") {
      requirePositive(draft.creditLimit, "creditLimit", errors);
      requireMoney(draft.openingDebt, "openingDebt", errors, true);
      const limit = DebtMoney.toMinor(draft.creditLimit);
      const openingDebt = DebtMoney.toMinor(draft.openingDebt);
      if (limit !== null && openingDebt !== null && openingDebt > limit) {
        errors.openingDebt = "Текущий долг не может превышать лимит.";
      }
    } else {
      requirePositive(draft.amount, "amount", errors);
      if (!draft.accountId) errors.accountId = "Выберите денежный счёт.";
      if (!draft.operationDate) errors.operationDate = "Укажите дату операции.";
    }
    return errors;
  }

  static build(draft: DebtCreateDraft): DebtCreateRequest {
    const common = {
      currency: draft.currency.trim().toUpperCase(),
      name: draft.name.trim(),
      notes: optional(draft.notes),
      openedOn: optional(draft.openedOn),
    };
    if (draft.action === "give_loan") {
      return {
        ...common,
        action: draft.action,
        amount: normalizeMoney(draft.amount),
        description: optional(draft.description),
        fundingAccountId: draft.accountId,
        maturityDate: optional(draft.maturityDate),
        operationDate: draft.operationDate,
      };
    }
    if (draft.action === "take_loan") {
      return {
        ...common,
        action: draft.action,
        amount: normalizeMoney(draft.amount),
        description: optional(draft.description),
        kind: draft.kind === "mortgage" ? "mortgage" : "loan_payable",
        maturityDate: optional(draft.maturityDate),
        operationDate: draft.operationDate,
        receivingAccountId: draft.accountId,
      };
    }
    if (draft.action === "open_credit_card") {
      return {
        ...common,
        action: draft.action,
        creditLimit: normalizeMoney(draft.creditLimit),
        openingDebt: normalizeMoney(draft.openingDebt),
      };
    }
    return {
      ...common,
      action: draft.action,
      kind:
        draft.kind === "loan_receivable"
          ? "loan_receivable"
          : draft.kind === "mortgage"
            ? "mortgage"
            : "loan_payable",
      maturityDate: optional(draft.maturityDate),
      openingBalance: normalizeMoney(draft.openingBalance),
      originalPrincipal: normalizeMoney(draft.originalPrincipal),
    };
  }

  static fieldErrors(errors: Record<string, string[]>): DebtCreateFieldErrors {
    const fields: Record<string, DebtCreateField> = {
      amount: "amount",
      credit_limit: "creditLimit",
      creditLimit: "creditLimit",
      currency: "currency",
      funding_account_id: "accountId",
      fundingAccountId: "accountId",
      maturity_date: "maturityDate",
      maturityDate: "maturityDate",
      name: "name",
      opening_balance: "openingBalance",
      opening_debt: "openingDebt",
      openingBalance: "openingBalance",
      openingDebt: "openingDebt",
      operation_date: "operationDate",
      operationDate: "operationDate",
      original_principal: "originalPrincipal",
      originalPrincipal: "originalPrincipal",
      receiving_account_id: "accountId",
      receivingAccountId: "accountId",
    };
    return Object.fromEntries(
      Object.entries(errors).flatMap(([field, messages]) => {
        const key = fields[field.split(".").at(-1) ?? ""];
        return key && messages[0] ? [[key, messages[0]]] : [];
      }),
    );
  }
}

function optional(value: string): string | null {
  return value.trim() || null;
}

function normalizeMoney(value: string): string {
  return value.trim().replace(",", ".");
}

export class DebtMoney {
  static toMinor(value: string): bigint | null {
    const match = /^(\d+)(?:[.,](\d{1,2}))?$/.exec(value.trim());
    if (!match?.[1]) return null;
    return BigInt(match[1]) * 100n + BigInt((match[2] ?? "").padEnd(2, "0"));
  }
}

function requireMoney(
  value: string,
  field: DebtCreateField,
  errors: DebtCreateFieldErrors,
  allowZero: boolean,
) {
  const amount = DebtMoney.toMinor(value);
  if (amount === null || (!allowZero && amount === 0n)) {
    errors[field] = allowZero
      ? "Введите неотрицательную сумму с точностью до двух знаков."
      : "Введите сумму больше нуля с точностью до двух знаков.";
  }
}

function requirePositive(
  value: string,
  field: DebtCreateField,
  errors: DebtCreateFieldErrors,
) {
  requireMoney(value, field, errors, false);
}

export function debtDirectionLabel(kind: DebtKind): string {
  return kind === "loan_receivable" ? "Должны мне" : "Должен я";
}
