import { useRef, useState, type FormEvent, type RefObject } from "react";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../../ui/field/field";
import { FormErrorSummary } from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import { accountTypeLabels } from "./account-labels";
import styles from "./account-list-page.module.css";
import {
  createAccount,
  type AccountSummaryDto,
  type AccountType,
  type CreateAccountDraft,
} from "./api/accounts-api";
import {
  accountDraftIsDirty,
  accountFieldErrors,
  accountFormSummaryErrors,
  emptyAccountDraft,
  firstInvalidAccountField,
  validateAccountDraft,
  type AccountFieldErrors,
} from "./account-form";

export function AccountCreatePanel({
  accountTypes,
  csrfToken,
  defaultCurrency,
  onClose,
  onCreated,
}: {
  accountTypes: AccountType[];
  csrfToken: string;
  defaultCurrency: string;
  onClose: () => void;
  onCreated: (account: AccountSummaryDto) => void;
}) {
  const initialDraft = emptyAccountDraft(accountTypes, defaultCurrency);
  const nameRef = useRef<HTMLInputElement>(null);
  const typeRef = useRef<HTMLSelectElement>(null);
  const currencyRef = useRef<HTMLInputElement>(null);
  const initialBalanceRef = useRef<HTMLInputElement>(null);
  const pendingRef = useRef(false);
  const [draft, setDraft] = useState<CreateAccountDraft>(initialDraft);
  const [fieldErrors, setFieldErrors] = useState<AccountFieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const summaryErrors = accountFormSummaryErrors(fieldErrors);

  function changeDraft<FieldName extends keyof CreateAccountDraft>(
    field: FieldName,
    value: CreateAccountDraft[FieldName],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current) return;
    const nextErrors = validateAccountDraft(draft);
    setFieldErrors(nextErrors);
    setSubmitError(null);
    const invalidField = firstInvalidAccountField(nextErrors);
    if (invalidField) {
      fieldRefs({ currencyRef, initialBalanceRef, nameRef, typeRef })[
        invalidField
      ].current?.focus();
      return;
    }

    pendingRef.current = true;
    setPending(true);
    const result = await createAccount({ csrfToken, draft });
    pendingRef.current = false;
    setPending(false);
    if (result.status === "success") {
      onCreated(result.account);
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    if (result.status === "forbidden") {
      setSubmitError(result.message);
      return;
    }
    const serverErrors = accountFieldErrors(result.fieldErrors);
    setFieldErrors(serverErrors);
    setSubmitError(result.message);
    const serverInvalidField = firstInvalidAccountField(serverErrors);
    if (serverInvalidField) {
      fieldRefs({ currencyRef, initialBalanceRef, nameRef, typeRef })[
        serverInvalidField
      ].current?.focus();
    }
  }

  function requestClose() {
    if (accountDraftIsDirty(draft, initialDraft)) {
      setConfirmClose(true);
      return;
    }
    onClose();
  }

  return (
    <>
      <WorkbenchPanel
        description="Название, тип, валюта и остаток до первой операции."
        disabled={pending}
        onClose={requestClose}
        title="Новый счёт"
      >
        <form
          className={styles.createForm}
          data-account-create
          noValidate
          onSubmit={submit}
        >
          {submitError || summaryErrors.length > 0 ? (
            <FormErrorSummary
              errors={summaryErrors}
              message={
                submitError ?? "Проверьте поля нового счёта и повторите."
              }
            />
          ) : null}
          <div className={styles.formGrid}>
            <Field
              error={fieldErrors.name}
              errorId="account-name-error"
              htmlFor="account-name"
              label="Название"
              required
            >
              <input
                ref={nameRef}
                id="account-name"
                aria-describedby={
                  fieldErrors.name ? "account-name-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.name)}
                autoFocus
                autoComplete="off"
                disabled={pending}
                maxLength={255}
                name="name"
                placeholder="Основная карта"
                required
                value={draft.name}
                onChange={(event) => changeDraft("name", event.target.value)}
              />
            </Field>
            <Field
              error={fieldErrors.accountType}
              errorId="account-type-error"
              htmlFor="account-type"
              label="Тип"
              required
            >
              <select
                ref={typeRef}
                id="account-type"
                aria-describedby={
                  fieldErrors.accountType ? "account-type-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.accountType)}
                disabled={pending}
                name="accountType"
                required
                value={draft.accountType}
                onChange={(event) =>
                  changeDraft("accountType", event.target.value as AccountType)
                }
              >
                {accountTypes.map((accountType) => (
                  <option key={accountType} value={accountType}>
                    {accountTypeLabels[accountType]}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              error={fieldErrors.currency}
              errorId="account-currency-error"
              hint="Трёхбуквенный код, например RUB."
              htmlFor="account-currency"
              label="Валюта"
              required
            >
              <input
                ref={currencyRef}
                id="account-currency"
                aria-describedby={
                  fieldErrors.currency ? "account-currency-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.currency)}
                autoCapitalize="characters"
                autoComplete="off"
                disabled={pending}
                maxLength={3}
                name="currency"
                required
                value={draft.currency}
                onChange={(event) =>
                  changeDraft("currency", event.target.value.toUpperCase())
                }
              />
            </Field>
            <Field
              error={fieldErrors.initialBalance}
              errorId="account-initial-balance-error"
              hint="Остаток до первой операции в Booker Tee."
              htmlFor="account-initial-balance"
              label="Начальный баланс"
              required
            >
              <input
                ref={initialBalanceRef}
                id="account-initial-balance"
                aria-describedby={
                  fieldErrors.initialBalance
                    ? "account-initial-balance-error"
                    : undefined
                }
                aria-invalid={Boolean(fieldErrors.initialBalance)}
                autoComplete="off"
                disabled={pending}
                inputMode="decimal"
                name="initialBalance"
                required
                value={draft.initialBalance}
                onChange={(event) =>
                  changeDraft("initialBalance", event.target.value)
                }
              />
            </Field>
          </div>
          <FormActions layout="split">
            <Button
              disabled={pending}
              onClick={requestClose}
              tone="secondary"
              type="button"
            >
              Отмена
            </Button>
            <Button
              disabled={pending}
              icon="plus"
              isLoading={pending}
              tone="primary"
              type="submit"
            >
              {pending ? "Создаём…" : "Создать счёт"}
            </Button>
          </FormActions>
        </form>
      </WorkbenchPanel>
      {confirmClose ? (
        <ConfirmationDialog
          cancelLabel="Продолжить создание"
          confirmLabel="Закрыть без сохранения"
          description="Несохранённые данные нового счёта будут потеряны."
          onCancel={() => setConfirmClose(false)}
          onConfirm={onClose}
          title="Закрыть создание счёта?"
        />
      ) : null}
    </>
  );
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
