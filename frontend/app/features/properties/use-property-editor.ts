import { useRef, useState, type FormEvent } from "react";

import type {
  CreatePropertyDraft,
  PropertySummaryDto,
} from "./api/properties-api";
import { loadProperties, updateProperty } from "./api/properties-api";
import {
  firstInvalidPropertyField,
  propertyFieldErrors,
  type PropertyFieldErrors,
  validatePropertyDraft,
} from "./property-form";

export type PropertyEditState = {
  conflict: boolean;
  draft: CreatePropertyDraft;
  fieldErrors: PropertyFieldErrors;
  pending: boolean;
  snapshot: PropertySummaryDto;
  submitError: string | null;
};

export function usePropertyEditor({
  csrfToken,
  onCommitted,
  onReloaded,
  showToast,
}: {
  csrfToken: string;
  onCommitted: (property: PropertySummaryDto) => void;
  onReloaded: (properties: PropertySummaryDto[]) => void;
  showToast: (toast: { message: string }) => void;
}) {
  const editTriggerRef = useRef<HTMLButtonElement | null>(null);
  const pendingSwitchRef = useRef<{
    property: PropertySummaryDto;
    trigger: HTMLButtonElement;
  } | null>(null);
  const [editState, setEditState] = useState<PropertyEditState | null>(null);
  const [confirmation, setConfirmation] = useState<"close" | "switch" | null>(
    null,
  );

  function beginEdit(property: PropertySummaryDto, trigger: HTMLButtonElement) {
    editTriggerRef.current = trigger;
    setEditState(propertyEditState(property));
    setConfirmation(null);
    pendingSwitchRef.current = null;
    focusEditField(property.id, "name");
  }

  function requestEdit(
    property: PropertySummaryDto,
    trigger: HTMLButtonElement,
  ) {
    if (editState?.pending) return;
    if (editState?.snapshot.id === property.id) {
      editTriggerRef.current = trigger;
      requestClose();
      return;
    }
    if (editState && propertyEditIsDirty(editState)) {
      pendingSwitchRef.current = { property, trigger };
      setConfirmation("switch");
      return;
    }
    beginEdit(property, trigger);
  }

  function requestClose() {
    if (!editState || editState.pending) return;
    if (propertyEditIsDirty(editState)) {
      setConfirmation("close");
      return;
    }
    closeEdit();
  }

  function closeEdit() {
    setEditState(null);
    setConfirmation(null);
    pendingSwitchRef.current = null;
    window.setTimeout(() => editTriggerRef.current?.focus(), 0);
  }

  function confirmDiscard() {
    const pendingSwitch = pendingSwitchRef.current;
    if (confirmation === "switch" && pendingSwitch) {
      beginEdit(pendingSwitch.property, pendingSwitch.trigger);
      return;
    }
    closeEdit();
  }

  function cancelDiscard() {
    setConfirmation(null);
    pendingSwitchRef.current = null;
  }

  function changeDraft(field: keyof CreatePropertyDraft, value: string) {
    setEditState((current) =>
      current
        ? {
            ...current,
            conflict: false,
            draft: { ...current.draft, [field]: value },
            fieldErrors: { ...current.fieldErrors, [field]: undefined },
            submitError: null,
          }
        : current,
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editState || editState.pending) return;
    const submitted = editState;
    const nextErrors = validatePropertyDraft(submitted.draft);
    const invalidField = firstInvalidPropertyField(nextErrors);
    if (invalidField) {
      setEditState({
        ...submitted,
        conflict: false,
        fieldErrors: nextErrors,
        submitError: null,
      });
      focusEditField(submitted.snapshot.id, invalidField);
      return;
    }

    setEditState({ ...submitted, pending: true, submitError: null });
    const result = await updateProperty({
      csrfToken,
      draft: {
        ...submitted.draft,
        expectedUpdatedAt: submitted.snapshot.updatedAt,
      },
      propertyId: submitted.snapshot.id,
    });
    if (result.status === "success") {
      onCommitted(result.property);
      showToast({ message: `Объект «${result.property.name}» изменён.` });
      setEditState(null);
      window.setTimeout(() => editTriggerRef.current?.focus(), 0);
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/properties");
      return;
    }
    if (result.status === "conflict") {
      setEditState({
        ...submitted,
        conflict: true,
        pending: false,
        submitError: result.message,
      });
      return;
    }
    if (result.status === "forbidden" || result.status === "not_found") {
      setEditState({
        ...submitted,
        conflict: false,
        pending: false,
        submitError: result.message,
      });
      return;
    }
    const serverErrors = propertyFieldErrors(result.fieldErrors);
    setEditState({
      ...submitted,
      conflict: false,
      fieldErrors: serverErrors,
      pending: false,
      submitError: result.message,
    });
    const invalidServerField = firstInvalidPropertyField(serverErrors);
    if (invalidServerField) {
      focusEditField(submitted.snapshot.id, invalidServerField);
    }
  }

  async function reloadSnapshot() {
    if (!editState || editState.pending) return;
    const propertyId = editState.snapshot.id;
    setEditState({ ...editState, pending: true });
    const result = await loadProperties();
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/properties");
      return;
    }
    if (result.status === "error") {
      setEditState((current) =>
        current
          ? { ...current, pending: false, submitError: result.message }
          : current,
      );
      return;
    }
    onReloaded(result.directory.items);
    const fresh = result.directory.items.find(
      (property) => property.id === propertyId,
    );
    if (!fresh) {
      setEditState((current) =>
        current
          ? {
              ...current,
              conflict: false,
              pending: false,
              submitError: "Объект больше не доступен.",
            }
          : current,
      );
      return;
    }
    setEditState(propertyEditState(fresh));
    focusEditField(propertyId, "name");
  }

  return {
    cancelDiscard,
    changeDraft,
    confirmDiscard,
    confirmation,
    editState,
    reloadSnapshot,
    requestClose,
    requestEdit,
    submit,
  };
}

function propertyEditState(property: PropertySummaryDto): PropertyEditState {
  return {
    conflict: false,
    draft: propertyDraft(property),
    fieldErrors: {},
    pending: false,
    snapshot: property,
    submitError: null,
  };
}

function propertyDraft(property: PropertySummaryDto): CreatePropertyDraft {
  return {
    name: property.name,
    shortName: property.shortName ?? "",
    address: property.address ?? "",
  };
}

function propertyEditIsDirty(state: PropertyEditState): boolean {
  const initial = propertyDraft(state.snapshot);
  return (
    state.draft.name !== initial.name ||
    state.draft.shortName !== initial.shortName ||
    state.draft.address !== initial.address
  );
}

function focusEditField(propertyId: string, field: keyof CreatePropertyDraft) {
  window.setTimeout(() => {
    const fields = Array.from(
      document.querySelectorAll<HTMLElement>(
        `[data-property-id="${propertyId}"][data-property-edit-field="${field}"]`,
      ),
    );
    (
      fields.find((element) => element.offsetParent !== null) ?? fields[0]
    )?.focus();
  }, 0);
}
