export function operationHref(operationId: string): string {
  const encodedId = encodeURIComponent(operationId);
  return `/operations?operation_id=${encodedId}#operation-${encodedId}`;
}
