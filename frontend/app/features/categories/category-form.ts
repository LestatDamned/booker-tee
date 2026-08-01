import type { CreateCategoryDraft } from "./api/categories-api";

export type CategoryFieldErrors = Partial<
  Record<keyof CreateCategoryDraft, string>
>;

export function validateCategoryDraft(
  draft: CreateCategoryDraft,
): CategoryFieldErrors {
  const errors: CategoryFieldErrors = {};
  const name = draft.name.trim();
  if (!name) {
    errors.name = "Введите название категории.";
  } else if (name.length > 255) {
    errors.name = "Название не должно быть длиннее 255 символов.";
  }
  if (draft.notes.trim().length > 1000) {
    errors.notes = "Заметка не должна быть длиннее 1000 символов.";
  }
  return errors;
}

export function categoryFieldErrors(
  fieldErrors: Record<string, string[]>,
): CategoryFieldErrors {
  const errors: CategoryFieldErrors = {};
  for (const field of ["name", "kind", "notes"] as const) {
    const message = fieldErrors[field]?.[0];
    if (message) errors[field] = message;
  }
  return errors;
}

export function firstInvalidCategoryField(
  errors: CategoryFieldErrors,
): keyof CreateCategoryDraft | null {
  for (const field of ["name", "kind", "notes"] as const) {
    if (errors[field]) return field;
  }
  return null;
}
