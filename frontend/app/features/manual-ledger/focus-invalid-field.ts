export function focusFirstInvalidField(container: HTMLElement | null): void {
  container?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
}
