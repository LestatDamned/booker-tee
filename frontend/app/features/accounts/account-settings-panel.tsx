import {
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type RefObject,
} from "react";

import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../../ui/field/field";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../../ui/field/form-error-summary";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import {
  changeAccountLifecycle,
  updateAccount,
  type AccountSummaryDto,
  type AccountType,
  type CreateAccountDraft,
} from "./api/accounts-api";
import type { AccountDetailDto } from "./api/account-detail-api";
import { validateAccountDraft, type AccountFieldErrors } from "./account-form";
import { accountTypeLabels } from "./account-detail-model";
import styles from "./account-settings-panel.module.css";

type Account = AccountDetailDto["account"];
type FieldErrors = AccountFieldErrors;

type Props = {
  account: Account;
  csrfToken: string;
  onClose: () => void;
  onCommitted: (account: AccountSummaryDto, message: string) => void;
};

const accountTypes: AccountType[] = [
  "cash",
  "card",
  "deposit",
  "checking",
  "other",
];

export function AccountSettingsPanel({
  account,
  csrfToken,
  onClose,
  onCommitted,
}: Props) {
  const initialDraft = useMemo(() => accountDraft(account), [account]);
  const [draft, setDraft] = useState(initialDraft);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [pending, setPending] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const typeRef = useRef<HTMLSelectElement>(null);
  const currencyRef = useRef<HTMLInputElement>(null);
  const initialBalanceRef = useRef<HTMLInputElement>(null);
  const dirty = !sameDraft(draft, initialDraft);
  const summaryErrors = formSummaryErrors(fieldErrors);

  function changeDraft<Key extends keyof CreateAccountDraft>(
    field: Key,
    value: CreateAccountDraft[Key],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
    setConflict(false);
  }

  function requestClose() {
    if (pending) return;
    if (dirty) {
      setConfirmClose(true);
      return;
    }
    onClose();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validateAccountDraft(draft);
    setFieldErrors(errors);
    setSubmitError(null);
    setConflict(false);
    const invalid = firstInvalidField(errors);
    if (invalid) {
      fieldRefs({
        currencyRef,
        initialBalanceRef,
        nameRef,
        typeRef,
      })[invalid].current?.focus();
      return;
    }

    setPending(true);
    const result = await updateAccount({
      accountId: account.id,
      csrfToken,
      draft: { ...draft, expectedUpdatedAt: account.updatedAt },
    });
    setPending(false);
    if (result.status === "success") {
      onCommitted(result.account, "Настройки счёта сохранены.");
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign(
        `/login?next=${encodeURIComponent(window.location.pathname)}`,
      );
      return;
    }
    if (result.status === "conflict") {
      setConflict(result.code === "account_update_conflict");
      setSubmitError(result.message);
      return;
    }
    if (result.status === "forbidden") {
      setSubmitError(result.message);
      return;
    }
    const serverErrors = accountFieldErrors(result.fieldErrors);
    setFieldErrors(serverErrors);
    setSubmitError(result.message);
    const serverInvalid = firstInvalidField(serverErrors);
    if (serverInvalid) {
      fieldRefs({
        currencyRef,
        initialBalanceRef,
        nameRef,
        typeRef,
      })[serverInvalid].current?.focus();
    }
  }

  async function runLifecycle(action: "archive" | "restore") {
    setPending(true);
    setSubmitError(null);
    const result = await changeAccountLifecycle({
      account,
      action,
      csrfToken,
    });
    setPending(false);
    if (result.status === "success") {
      onCommitted(
        result.account,
        action === "archive" ? "Счёт перенесён в архив." : "Счёт восстановлен.",
      );
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign(
        `/login?next=${encodeURIComponent(window.location.pathname)}`,
      );
      return;
    }
    setConfirmArchive(false);
    setSubmitError(result.message);
    setConflict(result.status === "conflict");
  }

  return (
    <>
      <WorkbenchPanel
        description="Основные сведения и финансовые параметры счёта."
        disabled={pending}
        onClose={requestClose}
        title="Настройки счёта"
      >
        <form
          className={styles.form}
          data-account-settings
          noValidate
          onSubmit={submit}
        >
          {(submitError || summaryErrors.length > 0) && (
            <FormErrorSummary
              errors={summaryErrors}
              message={
                submitError ?? "Проверьте поля счёта и повторите сохранение."
              }
            />
          )}
          {conflict ? (
            <Button onClick={() => window.location.reload()} type="button">
              Загрузить актуальные данные
            </Button>
          ) : null}

          <fieldset className={styles.group}>
            <legend>Основные сведения</legend>
            <Field
              error={fieldErrors.name}
              errorId="settings-account-name-error"
              htmlFor="settings-account-name"
              label="Название"
              required
            >
              <input
                aria-describedby={
                  fieldErrors.name ? "settings-account-name-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.name)}
                autoComplete="off"
                disabled={pending}
                id="settings-account-name"
                maxLength={255}
                onChange={(event) => changeDraft("name", event.target.value)}
                ref={nameRef}
                required
                value={draft.name}
              />
            </Field>
            <Field
              error={fieldErrors.accountType}
              errorId="settings-account-type-error"
              htmlFor="settings-account-type"
              label="Тип"
              required
            >
              <select
                aria-describedby={
                  fieldErrors.accountType
                    ? "settings-account-type-error"
                    : undefined
                }
                aria-invalid={Boolean(fieldErrors.accountType)}
                disabled={pending}
                id="settings-account-type"
                onChange={(event) =>
                  changeDraft("accountType", event.target.value as AccountType)
                }
                ref={typeRef}
                required
                value={draft.accountType}
              >
                {accountTypes.map((accountType) => (
                  <option key={accountType} value={accountType}>
                    {accountTypeLabels[accountType]}
                  </option>
                ))}
              </select>
            </Field>
          </fieldset>

          <fieldset className={styles.group}>
            <legend>Финансовые параметры</legend>
            <Field
              error={fieldErrors.currency}
              errorId="settings-account-currency-error"
              hint="После появления проводок валюту счёта изменить нельзя."
              htmlFor="settings-account-currency"
              label="Валюта"
              required
            >
              <input
                aria-describedby={
                  fieldErrors.currency
                    ? "settings-account-currency-error"
                    : undefined
                }
                aria-invalid={Boolean(fieldErrors.currency)}
                autoCapitalize="characters"
                autoComplete="off"
                disabled={pending}
                id="settings-account-currency"
                maxLength={3}
                onChange={(event) =>
                  changeDraft("currency", event.target.value.toUpperCase())
                }
                ref={currencyRef}
                required
                value={draft.currency}
              />
            </Field>
            <Field
              error={fieldErrors.initialBalance}
              errorId="settings-account-initial-balance-error"
              hint="Меняет текущий баланс на ту же разницу; проводки остаются без изменений."
              htmlFor="settings-account-initial-balance"
              label="Начальный баланс"
              required
            >
              <input
                aria-describedby={
                  fieldErrors.initialBalance
                    ? "settings-account-initial-balance-error"
                    : undefined
                }
                aria-invalid={Boolean(fieldErrors.initialBalance)}
                autoComplete="off"
                disabled={pending}
                id="settings-account-initial-balance"
                inputMode="decimal"
                onChange={(event) =>
                  changeDraft("initialBalance", event.target.value)
                }
                ref={initialBalanceRef}
                required
                value={draft.initialBalance}
              />
            </Field>
          </fieldset>

          <div className={styles.actions}>
            <Button disabled={pending} onClick={requestClose} type="button">
              Отмена
            </Button>
            <Button
              disabled={!dirty || pending}
              isLoading={pending}
              tone="primary"
              type="submit"
            >
              Сохранить изменения
            </Button>
          </div>

          <section
            aria-labelledby="account-management-title"
            className={styles.management}
          >
            <div>
              <h3 id="account-management-title">Управление счётом</h3>
              <p>История и баланс сохраняются при переносе счёта в архив.</p>
            </div>
            {account.capabilities.canArchive ? (
              <Button
                disabled={pending}
                onClick={() => setConfirmArchive(true)}
                tone="dangerSecondary"
                type="button"
              >
                Перенести в архив
              </Button>
            ) : account.capabilities.canRestore ? (
              <Button
                disabled={pending}
                isLoading={pending}
                onClick={() => void runLifecycle("restore")}
                tone="secondary"
                type="button"
              >
                Восстановить счёт
              </Button>
            ) : null}
          </section>
        </form>
      </WorkbenchPanel>

      {confirmClose ? (
        <ConfirmationDialog
          cancelLabel="Продолжить редактирование"
          confirmLabel="Закрыть без сохранения"
          description="Несохранённые изменения настроек будут потеряны."
          onCancel={() => setConfirmClose(false)}
          onConfirm={onClose}
          title="Закрыть настройки?"
        />
      ) : null}

      {confirmArchive ? (
        <ConfirmationDialog
          cancelLabel="Оставить активным"
          confirmLabel="Перенести в архив"
          description={`История и баланс счёта «${account.name}» сохранятся, но счёт нельзя будет выбирать для новых операций и импортов.`}
          onCancel={() => setConfirmArchive(false)}
          onConfirm={() => void runLifecycle("archive")}
          pending={pending}
          title="Перенести счёт в архив?"
        />
      ) : null}
    </>
  );
}

function accountDraft(account: Account): CreateAccountDraft {
  return {
    name: account.name,
    accountType: account.accountType,
    currency: account.currency,
    initialBalance: account.initialBalance,
  };
}

function sameDraft(left: CreateAccountDraft, right: CreateAccountDraft) {
  return (
    left.name === right.name &&
    left.accountType === right.accountType &&
    left.currency === right.currency &&
    left.initialBalance === right.initialBalance
  );
}

function accountFieldErrors(
  fieldErrors: Record<string, string[]>,
): FieldErrors {
  const errors: FieldErrors = {};
  const fields = ["accountType", "currency", "initialBalance", "name"] as const;
  for (const field of fields) {
    const message = fieldErrors[field]?.[0];
    if (message) errors[field] = message;
  }
  return errors;
}

function firstInvalidField(
  errors: FieldErrors,
): keyof CreateAccountDraft | null {
  for (const field of [
    "name",
    "accountType",
    "currency",
    "initialBalance",
  ] as const) {
    if (errors[field]) return field;
  }
  return null;
}

function fieldRefs({
  currencyRef,
  initialBalanceRef,
  nameRef,
  typeRef,
}: {
  currencyRef: RefObject<HTMLInputElement | null>;
  initialBalanceRef: RefObject<HTMLInputElement | null>;
  nameRef: RefObject<HTMLInputElement | null>;
  typeRef: RefObject<HTMLSelectElement | null>;
}): Record<keyof CreateAccountDraft, RefObject<HTMLElement | null>> {
  return {
    accountType: typeRef,
    currency: currencyRef,
    initialBalance: initialBalanceRef,
    name: nameRef,
  };
}

function formSummaryErrors(errors: FieldErrors): FormErrorSummaryItem[] {
  const fields: Array<{
    field: keyof CreateAccountDraft;
    fieldId: string;
    label: string;
  }> = [
    { field: "name", fieldId: "settings-account-name", label: "Название" },
    {
      field: "accountType",
      fieldId: "settings-account-type",
      label: "Тип",
    },
    {
      field: "currency",
      fieldId: "settings-account-currency",
      label: "Валюта",
    },
    {
      field: "initialBalance",
      fieldId: "settings-account-initial-balance",
      label: "Начальный баланс",
    },
  ];
  return fields.flatMap(({ field, fieldId, label }) =>
    errors[field] ? [{ fieldId, label, message: errors[field] }] : [],
  );
}
