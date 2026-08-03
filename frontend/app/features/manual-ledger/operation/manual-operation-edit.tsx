import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { useLocation, useNavigate } from "react-router";

import { redirectIfUnauthenticated } from "../../../session/unauthenticated";
import { Button } from "../../../ui/button/button";
import { FormErrorSummary } from "../../../ui/field/form-error-summary";
import { FormActions } from "../../../ui/field/form-layout";
import { InlineNotice } from "../../../ui/inline-notice/inline-notice";
import { RequestState } from "../../../ui/request-state/request-state";
import {
  loadManualOperationEdit,
  type ManualLedgerDto,
  type ManualOperationDto,
} from "../api/manual-ledger-api";
import { focusFirstInvalidField } from "../focus-invalid-field";
import { updateManualOperation } from "../api/manual-ledger-mutations";
import {
  editDraftFromOperation,
  manualOperationUpdateRequest,
  type ManualOperationDraft,
} from "./manual-operation-draft";
import {
  manualOperationErrorSummaryItems,
  ManualOperationFields,
} from "./manual-operation-form";
import styles from "../manual-ledger.module.css";

type ManualOperationEditProps = {
  csrfToken: string;
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
    if (redirectIfUnauthenticated(result)) return;
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
    if (!requested.current) {
      void loadSnapshot();
    }
  }, [loadSnapshot]);

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
      manualOperationUpdateRequest(submitted.draft, submitted.snapshot.version),
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
      onClose();
      if (!(alreadyTargeted && onUpdated)) {
        void navigate({
          pathname: location.pathname,
          search: `?${search.toString()}`,
          hash: `#operation-${result.operation.id}`,
        });
      }
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
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

  return (
    <section
      aria-busy={state.status === "loading"}
      className={styles.editPanel}
    >
      {state.status === "idle" || state.status === "loading" ? (
        <RequestState message="Загружаем актуальные данные…" />
      ) : null}
      {state.status === "load_error" ? (
        <InlineNotice
          action={
            <Button
              icon="retry"
              onClick={() => void loadSnapshot()}
              tone="secondary"
            >
              Повторить загрузку
            </Button>
          }
          role="alert"
          title="Не удалось загрузить операцию"
          tone="danger"
        >
          {state.message}
        </InlineNotice>
      ) : null}
      {state.status === "ready" ? (
        <form
          className={styles.operationForm}
          onSubmit={submitOperation}
          ref={formRef}
        >
          {state.submission.status === "validation_error" ? (
            <FormErrorSummary
              errors={manualOperationErrorSummaryItems(
                state.submission.fieldErrors,
                `manual-operation-edit-${operationId}`,
              )}
              headingLevel={4}
              message={state.submission.message}
              title="Не удалось сохранить изменения"
            />
          ) : null}
          {state.submission.status === "conflict" ? (
            <InlineNotice
              action={
                <Button
                  icon="retry"
                  onClick={() => void loadSnapshot()}
                  tone="secondary"
                >
                  Загрузить актуальную версию
                </Button>
              }
              role="alert"
              title="Операция уже была изменена"
              tone="danger"
            >
              {state.submission.message} Ваш draft сохранён на странице.
              Загрузка актуальной версии заменит его.
            </InlineNotice>
          ) : null}
          {state.submission.status === "error" ? (
            <InlineNotice
              action={
                <Button icon="retry" tone="secondary" type="submit">
                  Повторить сохранение
                </Button>
              }
              role="alert"
              title="Не удалось сохранить изменения"
              tone="danger"
            >
              {state.submission.message} Введённые значения остались в форме.
            </InlineNotice>
          ) : null}
          <ManualOperationFields
            draft={state.draft}
            fieldErrors={
              state.submission.status === "validation_error"
                ? state.submission.fieldErrors
                : {}
            }
            idPrefix={`manual-operation-edit-${operationId}`}
            layout="expanded"
            onChange={(draft) => setState({ ...state, draft })}
            options={state.options}
          />
          <FormActions layout="split">
            <Button
              disabled={disabled || state.submission.status === "pending"}
              onClick={cancelDraft}
              tone="secondary"
            >
              Отмена
            </Button>
            <Button
              disabled={disabled}
              isLoading={state.submission.status === "pending"}
              tone="primary"
              type="submit"
              icon="check"
            >
              Сохранить изменения
            </Button>
          </FormActions>
        </form>
      ) : null}
    </section>
  );
}
