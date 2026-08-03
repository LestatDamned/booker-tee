import type { FormEvent } from "react";

import { Button } from "../../ui/button/button";
import { FormError } from "../../ui/field/form-error";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type { ImportReviewDto } from "./api/import-review-api";
import type { ImportReviewCategoryReferenceDto } from "./api/import-review-mutations";
import {
  CategoryEditor,
  DraftCapability,
  DraftFields,
  OperationModeSwitch,
} from "./classification-fields";
import styles from "./classification-panel.module.css";
import { ConfirmPostingAction } from "./posting-actions";
import { TransferPanel } from "./transfer-panel";
import { useClassificationWorkflow } from "./use-classification-workflow";

type ClassificationPanelProps = {
  categories: ImportReviewDto["references"]["categories"];
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onCancel: () => void;
  onCategoryCreated: (category: ImportReviewCategoryReferenceDto) => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  onSuccess: (message: string) => void;
  properties: ImportReviewDto["references"]["properties"];
  readonly: boolean;
};

export function ClassificationPanel({
  categories,
  csrfToken,
  documentId,
  item,
  onCancel,
  onCategoryCreated,
  onReviewReconciled,
  onSuccess,
  properties,
  readonly,
}: ClassificationPanelProps) {
  const workflow = useClassificationWorkflow({
    csrfToken,
    documentId,
    item,
    onCancel,
    onCategoryCreated,
  });

  function handleCreateCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void workflow.createCategory();
  }

  return (
    <div className={styles.classificationPanelBody}>
      {readonly ? (
        <p>Изменение classification недоступно для вашей роли.</p>
      ) : (
        <>
          <OperationModeSwitch
            item={item}
            mode={workflow.mode}
            onChange={workflow.changeMode}
          />
          {workflow.mode === "transfer" ? (
            <TransferPanel
              key={workflow.resetVersion}
              csrfToken={csrfToken}
              documentId={documentId}
              item={item}
              onCancel={workflow.cancelChanges}
              onReviewReconciled={onReviewReconciled}
              onSelectionChange={workflow.setTransferSelection}
              onSuccess={onSuccess}
              selection={workflow.transferSelection}
            />
          ) : (
            <>
              <DraftFields
                categories={categories}
                categoryEditorOpen={workflow.categoryEditorOpen}
                categoryRef={workflow.categoryRef}
                draft={workflow.draft}
                fieldErrors={workflow.fieldErrors}
                itemId={item.id}
                onCreateCategory={() =>
                  workflow.setCategoryEditorOpen((open) => !open)
                }
                pending={workflow.pending}
                properties={properties}
                propertyRef={workflow.propertyRef}
                updateDraft={workflow.updateDraft}
              />
              {workflow.categoryEditorOpen ? (
                <CategoryEditor
                  categoryKind={workflow.categoryKind}
                  categoryName={workflow.categoryName}
                  categoryNameRef={workflow.categoryNameRef}
                  fieldErrors={workflow.fieldErrors}
                  itemId={item.id}
                  onKindChange={workflow.setCategoryKind}
                  onNameChange={workflow.setCategoryName}
                  onSubmit={handleCreateCategory}
                  pending={workflow.pending}
                />
              ) : null}
            </>
          )}
        </>
      )}
      {workflow.error ? (
        Object.keys(workflow.fieldErrors).length > 0 ? (
          <FormError announce>{workflow.error}</FormError>
        ) : (
          <InlineNotice
            action={
              workflow.failure === "category" ? (
                <Button
                  disabled={workflow.pending}
                  icon="retry"
                  onClick={workflow.retry}
                  tone="secondary"
                >
                  Повторить создание
                </Button>
              ) : (
                <Button
                  disabled={workflow.pending}
                  icon="retry"
                  onClick={workflow.retry}
                  tone="secondary"
                >
                  Повторить проверку
                </Button>
              )
            }
            role="alert"
            title={
              workflow.failure === "category"
                ? "Не удалось создать категорию"
                : "Не удалось проверить выбор"
            }
            tone="danger"
          >
            {workflow.error}
          </InlineNotice>
        )
      ) : null}
      {workflow.mode === "ordinary" ? (
        <section
          aria-label="Решение по операции"
          className={styles.reviewDecisionSummary}
        >
          <DraftCapability dirty={workflow.dirty} pending={workflow.pending} />
          {!readonly ? (
            <ConfirmPostingAction
              categoryName={
                categories.find(
                  (category) =>
                    category.id === workflow.evaluation.selection.categoryId,
                )?.name ?? "Выбранная категория"
              }
              csrfToken={csrfToken}
              dirty={workflow.dirty}
              documentId={documentId}
              evaluation={workflow.evaluation}
              item={item}
              key={workflow.resetVersion}
              onCancel={workflow.cancelChanges}
              onReviewReconciled={onReviewReconciled}
              onSuccess={onSuccess}
              propertyName={
                properties.find(
                  (property) =>
                    property.id === workflow.evaluation.selection.propertyId,
                )?.name ?? "Без объекта"
              }
            />
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
