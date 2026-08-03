import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { redirectIfUnauthenticated } from "../../../session/unauthenticated";
import { Button } from "../../../ui/button/button";
import { FormErrorSummary } from "../../../ui/field/form-error-summary";
import { FormActions } from "../../../ui/field/form-layout";
import type { ManualLedgerDto } from "../api/manual-ledger-api";
import { focusFirstInvalidField } from "../focus-invalid-field";
import { createManualOperation } from "../api/manual-ledger-mutations";
import {
  emptyManualOperationDraft,
  manualOperationCreateRequest,
  operationTypeLabel,
  type ManualOperationDraft,
} from "./manual-operation-draft";
import {
  manualOperationErrorSummaryItems,
  ManualOperationFields,
} from "./manual-operation-form";
import styles from "../manual-ledger.module.css";

type ManualOperationCreateProps = {
  csrfToken: string;
  onClose: () => void;
  onCreated?: () => void;
  onPendingChange?: (pending: boolean) => void;
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
  csrfToken,
  onClose,
  onCreated,
  onPendingChange,
  options,
}: ManualOperationCreateProps) {
  const navigate = useNavigate();
  const formRef = useRef<HTMLFormElement>(null);
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

  async function submitOperation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitState.status === "pending" || draft.operationType === "") {
      return;
    }
    setSubmitState({ status: "pending" });
    onPendingChange?.(true);
    const result = await createManualOperation(
      manualOperationCreateRequest(draft),
      csrfToken,
      idempotencyKey,
    );
    onPendingChange?.(false);
    if (result.status === "success") {
      onCreated?.();
      onClose();
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
    if (redirectIfUnauthenticated(result)) return;
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
    onClose();
  }

  const fieldErrors =
    submitState.status === "error" ? submitState.fieldErrors : {};
  const pending = submitState.status === "pending";

  return (
    <form
      className={styles.operationForm}
      id="manual-operation-create-panel"
      onSubmit={submitOperation}
      ref={formRef}
    >
      {submitState.status === "error" ? (
        <FormErrorSummary
          errors={manualOperationErrorSummaryItems(
            fieldErrors,
            "manual-operation",
          )}
          message={submitState.message}
          title="Не удалось создать операцию"
        />
      ) : null}
      <ManualOperationFields
        draft={draft}
        fieldErrors={fieldErrors}
        idPrefix="manual-operation"
        onChange={setDraft}
        options={options}
      />
      <FormActions layout="split">
        <Button disabled={pending} onClick={cancelDraft} tone="secondary">
          Отмена
        </Button>
        <Button
          disabled={draft.operationType === ""}
          isLoading={pending}
          tone="primary"
          type="submit"
          icon="plus"
        >
          Создать {operationTypeLabel(draft.operationType)}
        </Button>
      </FormActions>
    </form>
  );
}

function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
