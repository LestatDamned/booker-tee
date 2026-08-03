import { useRef, useState } from "react";

import {
  createImportReviewCategory,
  evaluateImportReviewDraft,
  type ImportReviewCategoryReferenceDto,
  type ImportReviewDraftEvaluationRequest,
} from "./api/import-review-mutations";
import {
  categoryMutationError,
  defaultCategoryKind,
  draftMutationError,
  serverClassificationDraft,
  serverClassificationEvaluation,
  type ClassificationItem,
  type ClassificationReviewMode,
} from "./classification-model";

type ClassificationFailure = "category" | "evaluation" | null;

export function useClassificationWorkflow({
  csrfToken,
  documentId,
  item,
  onCancel,
  onCategoryCreated,
}: {
  csrfToken: string;
  documentId: string;
  item: ClassificationItem;
  onCancel: () => void;
  onCategoryCreated: (category: ImportReviewCategoryReferenceDto) => void;
}) {
  const [draft, setDraft] = useState(() => serverClassificationDraft(item));
  const [evaluation, setEvaluation] = useState(() =>
    serverClassificationEvaluation(item),
  );
  const [dirty, setDirty] = useState(false);
  const [evaluationPending, setEvaluationPending] = useState(false);
  const [categoryPending, setCategoryPending] = useState(false);
  const [failure, setFailure] = useState<ClassificationFailure>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [categoryEditorOpen, setCategoryEditorOpen] = useState(false);
  const [categoryName, setCategoryName] = useState("");
  const [categoryKind, setCategoryKind] = useState<
    ImportReviewCategoryReferenceDto["kind"]
  >(defaultCategoryKind(item.classification.operationType));
  const [mode, setMode] = useState<ClassificationReviewMode>(() =>
    initialMode(item),
  );
  const [transferSelection, setTransferSelection] = useState("");
  const [resetVersion, setResetVersion] = useState(0);
  const categoryRef = useRef<HTMLInputElement>(null);
  const propertyRef = useRef<HTMLSelectElement>(null);
  const categoryNameRef = useRef<HTMLInputElement>(null);
  const evaluationRequestId = useRef(0);
  const categoryRequestId = useRef(0);

  const pending = evaluationPending || categoryPending;

  function clearFeedback() {
    setFailure(null);
    setError(null);
    setFieldErrors({});
  }

  async function runEvaluation(nextDraft = draft) {
    const currentRequestId = ++evaluationRequestId.current;
    setEvaluationPending(true);
    clearFeedback();
    const result = await evaluateImportReviewDraft(
      documentId,
      item.id,
      nextDraft,
      csrfToken,
    );
    if (currentRequestId !== evaluationRequestId.current) return;
    setEvaluationPending(false);
    if (result.status === "success") {
      setEvaluation(result.data);
      setDirty(false);
      return;
    }
    setFailure("evaluation");
    if (result.status === "validation_error") {
      setError(result.message);
      setFieldErrors(result.fieldErrors);
      focusDraftField(
        result.fieldErrors,
        categoryRef.current,
        propertyRef.current,
      );
      return;
    }
    setError(draftMutationError(result));
  }

  function updateDraft(nextDraft: ImportReviewDraftEvaluationRequest) {
    setDraft(nextDraft);
    setDirty(true);
    clearFeedback();
    void runEvaluation(nextDraft);
  }

  async function createCategory() {
    const currentRequestId = ++categoryRequestId.current;
    evaluationRequestId.current += 1;
    setEvaluationPending(false);
    setCategoryPending(true);
    clearFeedback();
    const result = await createImportReviewCategory(
      documentId,
      item.id,
      { name: categoryName, kind: categoryKind },
      csrfToken,
    );
    if (currentRequestId !== categoryRequestId.current) return;
    setCategoryPending(false);
    if (result.status === "success") {
      onCategoryCreated(result.data);
      const nextDraft = { ...draft, categoryId: result.data.id };
      setDraft(nextDraft);
      setCategoryName("");
      setCategoryEditorOpen(false);
      await runEvaluation(nextDraft);
      return;
    }
    setFailure("category");
    if (result.status === "validation_error") {
      setError(result.message);
      setFieldErrors(result.fieldErrors);
      categoryNameRef.current?.focus();
      return;
    }
    setError(categoryMutationError(result));
  }

  function changeMode(nextMode: ClassificationReviewMode) {
    setMode(nextMode);
    clearFeedback();
    if (nextMode === "ordinary") {
      void runEvaluation(draft);
    } else {
      setCategoryEditorOpen(false);
    }
  }

  function cancelChanges() {
    evaluationRequestId.current += 1;
    categoryRequestId.current += 1;
    setDraft(serverClassificationDraft(item));
    setEvaluation(serverClassificationEvaluation(item));
    setDirty(false);
    setEvaluationPending(false);
    setCategoryPending(false);
    clearFeedback();
    setCategoryEditorOpen(false);
    setCategoryName("");
    setCategoryKind(defaultCategoryKind(item.classification.operationType));
    setMode(initialMode(item));
    setTransferSelection("");
    setResetVersion((version) => version + 1);
    onCancel();
  }

  function retry() {
    if (failure === "category") void createCategory();
    else void runEvaluation(draft);
  }

  return {
    cancelChanges,
    categoryEditorOpen,
    categoryKind,
    categoryName,
    categoryNameRef,
    categoryRef,
    changeMode,
    createCategory,
    dirty,
    draft,
    error,
    evaluation,
    failure,
    fieldErrors,
    mode,
    pending,
    propertyRef,
    resetVersion,
    retry,
    setCategoryEditorOpen,
    setCategoryKind,
    setCategoryName,
    setTransferSelection,
    transferSelection,
    updateDraft,
  };
}

function initialMode(item: ClassificationItem): ClassificationReviewMode {
  return item.classification.operationType === "transfer"
    ? "transfer"
    : "ordinary";
}

function focusDraftField(
  fieldErrors: Record<string, string[]>,
  categoryInput: HTMLInputElement | null,
  propertyInput: HTMLSelectElement | null,
) {
  if (fieldErrors.categoryId) categoryInput?.focus();
  else if (fieldErrors.propertyId) propertyInput?.focus();
}
