import { z } from "zod";

import {
  apiLoadError,
  apiLoadNetworkError,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
  type ApiLoadError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import type { components } from "../../../api/generated/schema";
import { requestJson } from "../../../api/transport";
import { workspaceRoleSchema, workspaceTypeSchema } from "./workspaces-api";

export type WorkspaceActivityDto =
  components["schemas"]["WorkspaceActivityApiResponse"];
export type WorkspaceActivityItemDto = WorkspaceActivityDto["items"][number];
export type WorkspaceActivityCursorDto = NonNullable<
  WorkspaceActivityDto["nextCursor"]
>;
export type WorkspaceActivityScope = WorkspaceActivityCursorDto["scope"];

const eventTypeSchema = z.enum([
  "workspace_created",
  "workspace_updated",
  "workspace_deactivated",
  "workspace_restored",
  "invitation_created",
  "invitation_accepted",
  "invitation_revoked",
  "member_role_changed",
  "member_disabled",
  "member_reactivated",
  "member_left",
  "ownership_transferred",
  "manual_operation_created",
  "manual_operation_updated",
  "manual_operation_cancelled",
  "manual_operation_restored",
  "manual_operation_deleted",
  "import_review_item_confirmed",
  "import_review_transfer_created",
  "import_review_operation_linked",
  "import_review_posting_undone",
  "import_review_operation_unlinked",
  "imported_operation_updated",
  "debt_created",
  "debt_payment_recorded",
  "debt_payment_undone",
  "debt_updated",
  "debt_archived",
  "debt_restored",
  "debt_deleted",
  "document_uploaded",
]);
const memberStatusSchema = z.enum(["pending", "active", "disabled", "removed"]);
const operationTypeSchema = z.enum([
  "income",
  "expense",
  "transfer",
  "adjustment",
]);
const debtKindSchema = z.enum([
  "loan_receivable",
  "loan_payable",
  "credit_card",
  "mortgage",
]);
const actorSchema = z.object({ id: z.uuid(), displayName: z.string() });
const scopeSchema = z.enum(["all", "finance", "team"]);
const itemScopeSchema = z.enum(["finance", "team"]);
const entitySchema = z.object({
  type: z.enum(["workspace", "operation", "debt", "uploaded_document"]),
  id: z.uuid(),
  displayLabel: z.string().nullable(),
  isAvailable: z.boolean(),
});
const cursorSchema = z.object({
  beforeCreatedAt: z.iso.datetime({ offset: true }),
  beforeId: z.uuid(),
  scope: scopeSchema,
});

export const workspaceActivitySchema: z.ZodType<WorkspaceActivityDto> =
  z.object({
    workspaceId: z.uuid(),
    items: z.array(
      z.object({
        id: z.uuid(),
        eventType: eventTypeSchema,
        scope: itemScopeSchema,
        actor: actorSchema.nullable(),
        target: actorSchema.nullable(),
        entity: entitySchema.nullable(),
        summaryCode: eventTypeSchema,
        details: z.object({
          payloadVersion: z.number().int().nullable(),
          displayLabel: z.string().nullable(),
          operationType: operationTypeSchema.nullable(),
          documentId: z.uuid().nullable(),
          itemId: z.uuid().nullable(),
          affectedItemCount: z.number().int().nonnegative().nullable(),
          affectedDocumentCount: z.number().int().nonnegative().nullable(),
          debtKind: debtKindSchema.nullable(),
          paymentId: z.uuid().nullable(),
          displayFilename: z.string().nullable(),
          role: workspaceRoleSchema.nullable(),
          inviteeEmail: z.string().nullable(),
          oldRole: workspaceRoleSchema.nullable(),
          newRole: workspaceRoleSchema.nullable(),
          oldStatus: memberStatusSchema.nullable(),
          newStatus: memberStatusSchema.nullable(),
          oldName: z.string().nullable(),
          newName: z.string().nullable(),
          oldType: workspaceTypeSchema.nullable(),
          newType: workspaceTypeSchema.nullable(),
          oldDefaultCurrency: z.string().nullable(),
          newDefaultCurrency: z.string().nullable(),
          movedSessionCount: z.number().int().nonnegative().nullable(),
          revokedInvitationCount: z.number().int().nonnegative().nullable(),
        }),
        createdAt: z.iso.datetime({ offset: true }),
      }),
    ),
    nextCursor: cursorSchema.nullable(),
  });

export type WorkspaceActivityLoadResult =
  | { status: "success"; activity: WorkspaceActivityDto }
  | ApiUnauthenticatedFailure
  | { status: "forbidden" | "not_found"; message: string }
  | ApiLoadError;

export async function loadWorkspaceActivity(
  workspaceId: string,
  cursor?: WorkspaceActivityCursorDto,
  signal?: AbortSignal,
  scope: WorkspaceActivityScope = cursor?.scope ?? "all",
): Promise<WorkspaceActivityLoadResult> {
  const search = new URLSearchParams();
  search.set("scope", scope);
  if (cursor) {
    search.set("beforeCreatedAt", cursor.beforeCreatedAt);
    search.set("beforeId", cursor.beforeId);
  }
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/activity?${search}`,
    signal ? { signal } : undefined,
  );
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 403) {
    return { status: "forbidden", message: "Активность workspace недоступна." };
  }
  if (response.httpStatus === 404) {
    return { status: "not_found", message: "Workspace больше недоступен." };
  }
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = workspaceActivitySchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", activity: parsed.data }
    : apiLoadError("API вернул активность workspace неожиданного формата.");
}
