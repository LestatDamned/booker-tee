import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { useLocation, useNavigate } from "react-router";

import { Button } from "../../ui/button/button";
import { FormError } from "../../ui/field/form-error";
import {
  loadManualOperationEdit,
  type ManualLedgerDto,
  type ManualOperationDto,
} from "./manual-ledger-api";
import { focusFirstInvalidField } from "./focus-invalid-field";
import {
  updateManualOperation,
  type ManualOperationUpdateRequest,
} from "./manual-ledger-mutations";
import {
  editDraftFromOperation,
  ManualOperationFields,
  type ManualOperationDraft,
} from "./manual-operation-form";
import styles from "./manual-ledger.module.css";

type ManualOperationEditProps = {
  csrfToken: string;
  isOpen: boolean;
  disabled?: boolean;
  onClose: () => void;
  onPendingChange?: (pending: boolean) => void;
  onUpdated?: (operation: ManualOperationDto) => void;
  operationId: string;
};

type SubmissionState =
  | { status: "idle" }
  | { status: "pending" }
  | {
      status: "validation_error";
      message: string;
      fieldErrors: Record<string, string[]>;
    }
  | { status: "conflict"; message: string }
  | { status: "error"; message: string };

type EditState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "load_error"; message: string }
  | {
      status: "ready";
      snapshot: ManualOperationDto;
      draft: ManualOperationDraft;
      options: ManualLedgerDto["filterOptions"];
      submission: SubmissionState;
    };

export function ManualOperationEdit({
  csrfToken,
  disabled = false,
  isOpen,
  onClose,
  onPendingChange,
  onUpdated,
  operationId,
}: ManualOperationEditProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const requested = useRef(false);
  const formRef = useRef<HTMLFormElement>(null);
  const [state, setState] = useState<EditState>({ status: "idle" });
  const validationErrors =
    state.status === "ready" && state.submission.status === "validation_error"
      ? state.submission.fieldErrors
      : null;

  const loadSnapshot = useCallback(async () => {
    requested.current = true;
    setState({ status: "loading" });
    const result = await loadManualOperationEdit(operationId);
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/ledger/manual");
      return;
    }
    if (result.status === "error") {
      setState({ status: "load_error", message: result.message });
      return;
    }
    const draft = editDraftFromOperation(result.edit.operation);
    if (draft === null) {
      setState({
        status: "load_error",
        message: "Эту операцию нельзя открыть в форме редактирования.",
      });
      return;
    }
    setState({
      status: "ready",
      snapshot: result.edit.operation,
      draft,
      options: result.edit.filterOptions,
      submission: { status: "idle" },
    });
  }, [operationId]);

  useEffect(() => {
    if (isOpen && !requested.current) {
      void loadSnapshot();
    }
  }, [isOpen, loadSnapshot]);

  useEffect(() => {
    if (validationErrors !== null) {
      focusFirstInvalidField(formRef.current);
    }
  }, [validationErrors]);

  async function submitOperation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      disabled ||
      state.status !== "ready" ||
      state.submission.status === "pending"
    ) {
      return;
    }
    const submitted = state;
    setState({
      ...submitted,
      submission: { status: "pending" },
    });
    onPendingChange?.(true);
    const result = await updateManualOperation(
      operationId,
      updateRequest(submitted.draft, submitted.snapshot.version),
      csrfToken,
    );
    onPendingChange?.(false);
    if (result.status === "success") {
      const savedDraft = editDraftFromOperation(result.operation);
      if (savedDraft !== null) {
        setState({
          status: "ready",
          snapshot: result.operation,
          draft: savedDraft,
          options: submitted.options,
          submission: { status: "idle" },
        });
      }
      const search = new URLSearchParams(location.search);
      const alreadyTargeted =
        search.get("operation_id") === result.operation.id;
      search.set("operation_id", result.operation.id);
      onUpdated?.(result.operation);
      if (alreadyTargeted && onUpdated) {
        onClose();
      } else {
        void navigate({
          pathname: location.pathname,
          search: `?${search.toString()}`,
          hash: `#operation-${result.operation.id}`,
        });
      }
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/ledger/manual");
      return;
    }
    if (result.status === "validation_error") {
      setState({
        ...submitted,
        submission: {
          status: "validation_error",
          message: result.message,
          fieldErrors: result.fieldErrors,
        },
      });
      return;
    }
    setState({
      ...submitted,
      submission: { status: result.status, message: result.message },
    });
  }

  function cancelDraft() {
    if (state.status === "ready") {
      const draft = editDraftFromOperation(state.snapshot);
      if (draft !== null) {
        setState({ ...state, draft, submission: { status: "idle" } });
      }
    }
    onClose();
  }

  const panelId = `manual-operation-edit-panel-${operationId}`;
  return (
    <section
      aria-busy={state.status === "loading"}
      className={styles.editPanel}
      hidden={!isOpen}
      id={panelId}
    >
      <div className={styles.editHeader}>
        <div>
          <h3>Исправить операцию</h3>
          <p>Форма загружает свежую версию только при первом открытии.</p>
        </div>
        <Button disabled={disabled} onClick={onClose} tone="ghost">
          Закрыть
        </Button>
      </div>
      {state.status === "idle" || state.status === "loading" ? (
        <p>Загружаем актуальные данные…</p>
      ) : null}
      {state.status === "load_error" ? (
        <div className={styles.editFeedback}>
          <FormError announce>{state.message}</FormError>
          <Button onClick={() => void loadSnapshot()} tone="secondary">
            Повторить загрузку
          </Button>
        </div>
      ) : null}
      {state.status === "ready" ? (
        <form onSubmit={submitOperation} ref={formRef}>
          {state.submission.status === "validation_error" ||
          state.submission.status === "conflict" ||
          state.submission.status === "error" ? (
            <FormError announce>{state.submission.message}</FormError>
          ) : null}
          {state.submission.status === "conflict" ? (
            <div className={styles.editFeedback}>
              <p>Ваш draft сохранён. Загрузка актуальной версии заменит его.</p>
              <Button onClick={() => void loadSnapshot()} tone="secondary">
                Загрузить актуальную версию
              </Button>
            </div>
          ) : null}
          <ManualOperationFields
            draft={state.draft}
            fieldErrors={
              state.submission.status === "validation_error"
                ? state.submission.fieldErrors
                : {}
            }
            idPrefix={`manual-operation-edit-${operationId}`}
            onChange={(draft) => setState({ ...state, draft })}
            options={state.options}
          />
          <div className={styles.createActions}>
            <Button
              disabled={disabled}
              isLoading={state.submission.status === "pending"}
              tone="primary"
              type="submit"
            >
              Сохранить изменения
            </Button>
            <Button
              disabled={disabled || state.submission.status === "pending"}
              onClick={cancelDraft}
              tone="ghost"
            >
              Отмена
            </Button>
          </div>
        </form>
      ) : null}
    </section>
  );
}

function updateRequest(
  draft: ManualOperationDraft,
  version: number,
): ManualOperationUpdateRequest {
  const common = {
    amount: draft.amount,
    operationDate: draft.operationDate,
    description: draft.description,
    version,
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
