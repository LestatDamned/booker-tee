import { useRef, useState, type FormEvent } from "react";

import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import {
  loadCategoryDetail,
  updateCategory,
  type CategoryDetailDto,
  type UpdateCategoryDraft,
} from "./api/category-detail-api";
import {
  categoryFieldErrors,
  firstInvalidCategoryField,
  type CategoryFieldErrors,
  validateCategoryDraft,
} from "./category-form";

export type CategoryEditState = {
  conflict: boolean;
  draft: UpdateCategoryDraft;
  fieldErrors: CategoryFieldErrors;
  pending: boolean;
  snapshot: CategoryDetailDto;
  submitError: string | null;
};

export function useCategoryEditor({
  apiSearch,
  csrfToken,
  onCommitted,
  onReloaded,
  showToast,
}: {
  apiSearch: string;
  csrfToken: string;
  onCommitted: (detail: CategoryDetailDto) => void;
  onReloaded: (detail: CategoryDetailDto) => void;
  showToast: (toast: { message: string }) => void;
}) {
  const editTriggerRef = useRef<HTMLButtonElement | null>(null);
  const [editState, setEditState] = useState<CategoryEditState | null>(null);
  const [confirmation, setConfirmation] = useState<"close" | "kind" | null>(
    null,
  );

  function beginEdit(detail: CategoryDetailDto, trigger: HTMLButtonElement) {
    if (!detail.category.capabilities.canUpdate) return;
    editTriggerRef.current = trigger;
    setEditState(categoryEditState(detail));
    setConfirmation(null);
    focusCategoryEditField("name");
  }

  function changeDraft(
    field: keyof UpdateCategoryDraft,
    value: UpdateCategoryDraft[keyof UpdateCategoryDraft],
  ) {
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

  function requestClose() {
    if (!editState || editState.pending) return;
    if (categoryEditIsDirty(editState)) {
      setConfirmation("close");
      return;
    }
    closeEdit();
  }

  function closeEdit() {
    setEditState(null);
    setConfirmation(null);
    window.setTimeout(() => editTriggerRef.current?.focus(), 0);
  }

  function cancelConfirmation() {
    setConfirmation(null);
  }

  function confirmDiscard() {
    closeEdit();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editState || editState.pending) return;
    const submitted = editState;
    const nextErrors = validateCategoryDraft(submitted.draft);
    const invalidField = firstInvalidCategoryField(nextErrors);
    if (invalidField) {
      setEditState({
        ...submitted,
        conflict: false,
        fieldErrors: nextErrors,
        submitError: null,
      });
      focusCategoryEditField(invalidField);
      return;
    }
    const kindChanged =
      submitted.draft.kind !== submitted.snapshot.category.kind;
    if (
      kindChanged &&
      submitted.snapshot.kindChangeImpact.requiresConfirmation
    ) {
      setConfirmation("kind");
      return;
    }
    await commit(submitted);
  }

  async function confirmKindChange() {
    if (!editState) return;
    setConfirmation(null);
    await commit(editState);
  }

  async function commit(submitted: CategoryEditState) {
    setEditState({ ...submitted, pending: true, submitError: null });
    const result = await updateCategory({
      categoryId: submitted.snapshot.category.id,
      csrfToken,
      draft: submitted.draft,
      expectedUpdatedAt: submitted.snapshot.category.updatedAt,
      search: apiSearch,
    });
    if (result.status === "success") {
      onCommitted(result.detail);
      showToast({
        message: `Категория «${result.detail.category.name}» изменена.`,
      });
      setEditState(null);
      window.setTimeout(() => editTriggerRef.current?.focus(), 0);
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
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
    const serverErrors = categoryFieldErrors(result.fieldErrors);
    setEditState({
      ...submitted,
      conflict: false,
      fieldErrors: serverErrors,
      pending: false,
      submitError: result.message,
    });
    const invalidServerField = firstInvalidCategoryField(serverErrors);
    if (invalidServerField) focusCategoryEditField(invalidServerField);
  }

  async function reloadSnapshot() {
    if (!editState || editState.pending) return;
    const submitted = editState;
    setEditState({ ...submitted, pending: true });
    const result = await loadCategoryDetail(
      submitted.snapshot.category.id,
      apiSearch,
    );
    if (redirectIfUnauthenticated(result)) return;
    if (result.status !== "success") {
      setEditState((current) =>
        current
          ? {
              ...current,
              pending: false,
              submitError:
                result.status === "not_found"
                  ? "Категория больше не доступна."
                  : result.message,
            }
          : current,
      );
      return;
    }
    onReloaded(result.detail);
    setEditState({
      ...submitted,
      conflict: false,
      pending: false,
      snapshot: result.detail,
      submitError: null,
    });
    focusCategoryEditField("name");
  }

  return {
    beginEdit,
    cancelConfirmation,
    changeDraft,
    confirmation,
    confirmDiscard,
    confirmKindChange,
    editState,
    reloadSnapshot,
    requestClose,
    submit,
  };
}

function categoryEditState(detail: CategoryDetailDto): CategoryEditState {
  return {
    conflict: false,
    draft: categoryDraft(detail),
    fieldErrors: {},
    pending: false,
    snapshot: detail,
    submitError: null,
  };
}

function categoryDraft(detail: CategoryDetailDto): UpdateCategoryDraft {
  return {
    name: detail.category.name,
    kind: detail.category.kind,
    notes: detail.category.notes ?? "",
  };
}

function categoryEditIsDirty(state: CategoryEditState): boolean {
  const initial = categoryDraft(state.snapshot);
  return (
    state.draft.name !== initial.name ||
    state.draft.kind !== initial.kind ||
    state.draft.notes !== initial.notes
  );
}

function focusCategoryEditField(field: keyof UpdateCategoryDraft) {
  window.setTimeout(() => {
    document.getElementById(`category-edit-${field}`)?.focus();
  }, 0);
}
