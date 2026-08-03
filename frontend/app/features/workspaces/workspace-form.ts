import type { CreateWorkspaceDraft } from "./api/workspaces-api";

export type WorkspaceFieldErrors = Partial<
  Record<keyof CreateWorkspaceDraft, string>
>;

export function validateWorkspaceDraft(
  draft: CreateWorkspaceDraft,
): WorkspaceFieldErrors {
  const errors: WorkspaceFieldErrors = {};
  const name = draft.name.trim();
  if (!name) {
    errors.name = "Введите название пространства.";
  } else if (name.length > 255) {
    errors.name = "Название не должно быть длиннее 255 символов.";
  }
  if (!draft.workspaceType) errors.workspaceType = "Выберите тип пространства.";
  if (!/^[A-Z]{3}$/.test(draft.defaultCurrency)) {
    errors.defaultCurrency = "Выберите основную валюту.";
  }
  return errors;
}

export function workspaceFieldErrors(
  fieldErrors: Record<string, string[]>,
): WorkspaceFieldErrors {
  const errors: WorkspaceFieldErrors = {};
  for (const field of ["name", "workspaceType", "defaultCurrency"] as const) {
    const message = fieldErrors[field]?.[0];
    if (message) errors[field] = message;
  }
  return errors;
}

export function firstInvalidWorkspaceField(
  errors: WorkspaceFieldErrors,
): keyof CreateWorkspaceDraft | null {
  for (const field of ["name", "workspaceType", "defaultCurrency"] as const) {
    if (errors[field]) return field;
  }
  return null;
}
