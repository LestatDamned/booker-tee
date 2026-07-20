import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { Button } from "../../ui/button/button";
import { FormError } from "../../ui/field/form-error";
import type { ManualLedgerDto } from "./manual-ledger-api";
import { focusFirstInvalidField } from "./focus-invalid-field";
import {
  createManualOperation,
  type ManualOperationCreateRequest,
} from "./manual-ledger-mutations";
import {
  emptyManualOperationDraft,
  ManualOperationFields,
  operationTypeLabel,
  type ManualOperationDraft,
} from "./manual-operation-form";
import styles from "./manual-ledger.module.css";

type ManualOperationCreateProps = {
  canCreate: boolean;
  csrfToken: string;
  options: ManualLedgerDto["filterOptions"];
};

type SubmitState =
  | { status: "idle" }
  | { status: "pending" }
  | {
      status: "error";
      message: string;
      fieldErrors: Record<string, string[]>;
    };

export function ManualOperationCreate({
  canCreate,
  csrfToken,
  options,
}: ManualOperationCreateProps) {
  const navigate = useNavigate();
  const disclosureRef = useRef<HTMLButtonElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState<ManualOperationDraft>(
    emptyManualOperationDraft,
  );
  const [submitState, setSubmitState] = useState<SubmitState>({
    status: "idle",
  });
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey);

  useEffect(() => {
    if (
      submitState.status === "error" &&
      Object.keys(submitState.fieldErrors).length > 0
    ) {
      focusFirstInvalidField(formRef.current);
    }
  }, [submitState]);

  if (!canCreate) {
    return null;
  }

  async function submitOperation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitState.status === "pending") {
      return;
    }
    setSubmitState({ status: "pending" });
    const result = await createManualOperation(
      createRequest(draft),
      csrfToken,
      idempotencyKey,
    );
    if (result.status === "success") {
      setIsOpen(false);
      setDraft(emptyManualOperationDraft());
      setIdempotencyKey(newIdempotencyKey());
      setSubmitState({ status: "idle" });
      void navigate({
        pathname: "/ledger/manual",
        search: `?operation_id=${result.operation.id}`,
        hash: `#operation-${result.operation.id}`,
      });
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/ledger/manual");
      return;
    }
    setSubmitState({
      status: "error",
      message: result.message,
      fieldErrors:
        result.status === "validation_error" ? result.fieldErrors : {},
    });
  }

  function cancelDraft() {
    setDraft(emptyManualOperationDraft());
    setIdempotencyKey(newIdempotencyKey());
    setSubmitState({ status: "idle" });
    setIsOpen(false);
    queueMicrotask(() => disclosureRef.current?.focus());
  }

  const fieldErrors =
    submitState.status === "error" ? submitState.fieldErrors : {};
  const pending = submitState.status === "pending";

  return (
    <section className={styles.createRegion}>
      <div className={styles.createHeader}>
        <div>
          <h2>Новая операция</h2>
          <p>
            Операция будет проверена и сохранена backend как подтверждённая.
          </p>
        </div>
        <Button
          aria-controls="manual-operation-create-panel"
          aria-expanded={isOpen}
          onClick={() => setIsOpen((current) => !current)}
          ref={disclosureRef}
          tone="primary"
        >
          {isOpen ? "Скрыть" : "Добавить операцию"}
        </Button>
      </div>

      {isOpen ? (
        <form
          id="manual-operation-create-panel"
          onSubmit={submitOperation}
          ref={formRef}
        >
          {submitState.status === "error" ? (
            <FormError announce>{submitState.message}</FormError>
          ) : null}
          <ManualOperationFields
            draft={draft}
            fieldErrors={fieldErrors}
            idPrefix="manual-operation"
            onChange={setDraft}
            options={options}
          />
          <div className={styles.createActions}>
            <Button isLoading={pending} tone="primary" type="submit">
              Создать {operationTypeLabel(draft.operationType)}
            </Button>
            <Button disabled={pending} onClick={cancelDraft} tone="ghost">
              Отмена
            </Button>
          </div>
        </form>
      ) : null}
    </section>
  );
}

function createRequest(
  draft: ManualOperationDraft,
): ManualOperationCreateRequest {
  const common = {
    amount: draft.amount,
    operationDate: draft.operationDate,
    description: draft.description,
  };
  if (draft.operationType === "transfer") {
    return {
      ...common,
      operationType: "transfer",
      sourceAccountId: draft.accountId,
      destinationAccountId: draft.destinationAccountId,
    };
  }
  return {
    ...common,
    operationType: draft.operationType,
    accountId: draft.accountId,
    categoryId: draft.categoryId || null,
    propertyId: draft.propertyId || null,
  };
}

function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
