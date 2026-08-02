import { type FormEvent, type RefObject, useRef, useState } from "react";

import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import {
  loadTransactionRuleForEdit,
  type TransactionRuleEditDto,
  type TransactionRuleSummaryDto,
  updateTransactionRule,
} from "./api/transaction-rules-api";
import { TransactionRuleEditPanel } from "./transaction-rule-edit-panel";
import {
  focusFirstTransactionRuleError,
  normalizeTransactionRuleFieldErrors,
  transactionRuleDraftFromItem,
  transactionRuleUpdateRequest,
  type TransactionRuleDraft,
  validateTransactionRuleDraft,
} from "./transaction-rule-form";

type Variant = "desktop" | "mobile";
type RequestedEditor = {
  ruleId: string;
  trigger: HTMLButtonElement;
  variant: Variant;
};

export function useTransactionRuleEditor({
  csrfToken,
  onCommitted,
}: {
  csrfToken: string;
  onCommitted: (item: TransactionRuleSummaryDto) => void;
}) {
  const [opened, setOpened] = useState<RequestedEditor | null>(null);
  const [source, setSource] = useState<TransactionRuleEditDto | null>(null);
  const [draft, setDraft] = useState<TransactionRuleDraft | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const nextEditor = useRef<RequestedEditor | null>(null);
  const dirty = Boolean(
    source &&
    draft &&
    JSON.stringify(draft) !==
      JSON.stringify(transactionRuleDraftFromItem(source.item)),
  );

  async function load(requested: RequestedEditor) {
    setOpened(requested);
    setLoading(true);
    setMessage(null);
    setConflict(false);
    setErrors({});
    setSource(null);
    setDraft(null);
    const result = await loadTransactionRuleForEdit(requested.ruleId);
    setLoading(false);
    if (result.status !== "success") {
      setMessage(result.message);
      return;
    }
    setSource(result.value);
    setDraft(transactionRuleDraftFromItem(result.value.item));
    queueMicrotask(() =>
      document
        .getElementById(
          `rule-edit-${requested.variant}-${requested.ruleId}-pattern`,
        )
        ?.focus(),
    );
  }
  function requestOpen(
    ruleId: string,
    variant: Variant,
    trigger: HTMLButtonElement,
  ) {
    if (opened?.ruleId === ruleId && opened.variant === variant) {
      requestClose();
      return;
    }
    const requested = { ruleId, variant, trigger };
    if (dirty) {
      nextEditor.current = requested;
      setConfirmDiscard(true);
      return;
    }
    void load(requested);
  }
  function finishClose() {
    const trigger = opened?.trigger;
    setOpened(null);
    setSource(null);
    setDraft(null);
    setMessage(null);
    setConflict(false);
    queueMicrotask(() => trigger?.focus());
  }
  function requestClose() {
    if (dirty) {
      nextEditor.current = null;
      setConfirmDiscard(true);
    } else finishClose();
  }
  function discard() {
    setConfirmDiscard(false);
    const requested = nextEditor.current;
    nextEditor.current = null;
    if (requested) void load(requested);
    else finishClose();
  }
  function change<Field extends keyof TransactionRuleDraft>(
    field: Field,
    value: TransactionRuleDraft[Field],
  ) {
    setDraft((current) => (current ? { ...current, [field]: value } : current));
    setErrors((current) => ({ ...current, [field]: "" }));
    setMessage(null);
    setConflict(false);
  }
  async function reload() {
    if (opened) await load(opened);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!opened || !source || !draft) return;
    const clientErrors = validateTransactionRuleDraft(draft);
    setErrors(clientErrors);
    const prefix = `rule-edit-${opened.variant}-${opened.ruleId}`;
    if (Object.keys(clientErrors).length) {
      focusFirstTransactionRuleError(clientErrors, prefix);
      return;
    }
    setPending(true);
    setMessage(null);
    setConflict(false);
    const result = await updateTransactionRule(
      opened.ruleId,
      transactionRuleUpdateRequest(draft, source.item.updatedAt),
      csrfToken,
    );
    setPending(false);
    if (result.status === "success") {
      onCommitted(result.value);
      finishClose();
      return;
    }
    if (result.status === "validation_error") {
      const serverErrors = normalizeTransactionRuleFieldErrors(
        result.fieldErrors,
      );
      setErrors(serverErrors);
      setMessage(result.message);
      focusFirstTransactionRuleError(serverErrors, prefix);
      return;
    }
    setMessage(result.message);
    setConflict(result.status === "conflict");
  }
  const panel = opened ? (
    <TransactionRuleEditPanel
      conflict={conflict}
      draft={draft}
      errors={errors}
      loadError={message}
      loading={loading}
      onChange={change}
      onClose={requestClose}
      onReload={() => void reload()}
      onSubmit={submit}
      pending={pending}
      ruleId={opened.ruleId}
      source={source}
      variant={opened.variant}
    />
  ) : null;
  const dialog = confirmDiscard ? (
    <ConfirmationDialog
      cancelLabel="Продолжить редактирование"
      confirmLabel="Отбросить изменения"
      description="Несохранённые изменения правила будут потеряны."
      onCancel={() => {
        nextEditor.current = null;
        setConfirmDiscard(false);
      }}
      onConfirm={discard}
      returnFocusRef={
        { current: opened?.trigger ?? null } as RefObject<HTMLElement | null>
      }
      title="Отбросить изменения правила?"
    />
  ) : null;
  return { dialog, opened, panel, requestOpen };
}
