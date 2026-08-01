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
