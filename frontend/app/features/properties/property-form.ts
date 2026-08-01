import type { CreatePropertyDraft } from "./api/properties-api";

export type PropertyFieldErrors = Partial<
  Record<keyof CreatePropertyDraft, string>
>;

export function validatePropertyDraft(
  draft: CreatePropertyDraft,
): PropertyFieldErrors {
  const errors: PropertyFieldErrors = {};
  const name = draft.name.trim();
  if (!name) {
    errors.name = "Введите название объекта.";
  } else if (name.length > 255) {
    errors.name = "Название не должно быть длиннее 255 символов.";
  }
  if (draft.shortName.trim().length > 64) {
    errors.shortName = "Короткое имя не должно быть длиннее 64 символов.";
  }
  return errors;
}

export function propertyFieldErrors(
  fieldErrors: Record<string, string[]>,
): PropertyFieldErrors {
  const errors: PropertyFieldErrors = {};
  for (const field of ["name", "shortName", "address"] as const) {
    const message = fieldErrors[field]?.[0];
    if (message) errors[field] = message;
  }
  return errors;
}

export function firstInvalidPropertyField(
  errors: PropertyFieldErrors,
): keyof CreatePropertyDraft | null {
  for (const field of ["name", "shortName", "address"] as const) {
    if (errors[field]) return field;
  }
  return null;
}
