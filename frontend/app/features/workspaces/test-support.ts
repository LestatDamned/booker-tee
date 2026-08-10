import type { SessionDto } from "../../api/session";
import type { WorkspaceActivityDto } from "./api/workspace-activity-api";
import type { WorkspaceDirectoryDto } from "./api/workspaces-api";
import type { WorkspaceSettingsDto } from "./api/workspace-settings-api";
import type { WorkspaceMembersDto } from "./api/workspace-members-api";
import type { WorkspaceInvitationsDto } from "./api/workspace-invitations-api";

export const session: SessionDto = {
  user: {
    id: "f4835818-f111-41d6-a59d-62f541ace357",
    email: "max@example.test",
    name: "Max",
  },
  workspace: {
    id: "c12c9ac8-6851-4467-b87a-da7fc70586c8",
    name: "Дом",
    type: "personal",
    defaultCurrency: "RUB",
  },
  membership: { role: "owner", status: "active" },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canViewRawImportData: true,
    canViewMemberDirectory: true,
    canManageMembers: true,
    canViewWorkspaceActivity: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};

const updatedAt = "2026-08-03T08:30:00Z";

export const workspaceDirectory: WorkspaceDirectoryDto = {
  currentWorkspaceId: session.workspace.id,
  capabilities: { canCreate: true },
  workspaceTypeOptions: [
    { value: "personal", label: "Личное" },
    { value: "family", label: "Семейное" },
    { value: "project", label: "Проект" },
  ],
  currencyOptions: [
    { value: "RUB", label: "RUB — российский рубль" },
    { value: "USD", label: "USD — доллар США" },
  ],
  items: [
    {
      id: session.workspace.id,
      name: "Дом",
      type: "personal",
      defaultCurrency: "RUB",
      isActive: true,
      archivedAt: null,
      updatedAt,
      membership: { role: "owner", status: "active", updatedAt },
      isCurrent: true,
      capabilities: {
        canSelect: false,
        canUpdate: true,
        canManageMembers: true,
        canInvite: true,
        canLeave: false,
        canDeactivate: true,
        canRestore: false,
      },
      blockingReasonCodes: ["workspace_current"],
    },
    {
      id: "b52c52d4-6d94-4a33-b5f1-0a0943a75727",
      name: "Семейный бюджет",
      type: "family",
      defaultCurrency: "RUB",
      isActive: true,
      archivedAt: null,
      updatedAt,
      membership: { role: "editor", status: "active", updatedAt },
      isCurrent: false,
      capabilities: {
        canSelect: true,
        canUpdate: false,
        canManageMembers: false,
        canInvite: false,
        canLeave: true,
        canDeactivate: false,
        canRestore: false,
      },
      blockingReasonCodes: [],
    },
    {
      id: "25fa47a3-c9e5-424f-8348-978984cba9cf",
      name: "Архив проекта",
      type: "project",
      defaultCurrency: "USD",
      isActive: false,
      archivedAt: updatedAt,
      updatedAt,
      membership: { role: "viewer", status: "active", updatedAt },
      isCurrent: false,
      capabilities: {
        canSelect: false,
        canUpdate: false,
        canManageMembers: false,
        canInvite: false,
        canLeave: false,
        canDeactivate: false,
        canRestore: false,
      },
      blockingReasonCodes: ["workspace_inactive"],
    },
  ],
};

export const selectSuccessPayload = {
  session: {
    ...session,
    workspace: {
      id: workspaceDirectory.items[1]!.id,
      name: workspaceDirectory.items[1]!.name,
      type: "family",
      defaultCurrency: "RUB",
    },
    membership: { role: "editor", status: "active" },
  },
  navigationOutcome: {
    kind: "workspace_changed",
    href: "/app/workspaces",
    boundary: "hard_reload",
  },
};

export const createSuccessPayload = {
  workspace: {
    ...workspaceDirectory.items[0],
    id: "e359ccf9-dd0d-45d4-8aa4-bcbe80aa7edf",
    name: "Новый проект",
    type: "project",
  },
  session: {
    ...session,
    workspace: {
      id: "e359ccf9-dd0d-45d4-8aa4-bcbe80aa7edf",
      name: "Новый проект",
      type: "project",
      defaultCurrency: "RUB",
    },
  },
  navigationOutcome: {
    kind: "workspace_changed",
    href: "/app/workspaces",
    boundary: "hard_reload",
  },
  replayed: false,
};

export const workspaceSettings: WorkspaceSettingsDto = {
  workspace: {
    id: session.workspace.id,
    name: "Дом",
    type: "personal",
    defaultCurrency: "RUB",
    isActive: true,
    archivedAt: null,
    updatedAt,
    membership: { role: "owner", status: "active", updatedAt },
    capabilities: {
      canUpdate: true,
      canViewMemberDirectory: true,
      canViewWorkspaceActivity: true,
      canManageMembers: true,
      canInvite: true,
      canDeactivate: true,
      canRestore: false,
    },
    blockingReasonCodes: [],
  },
  workspaceTypeOptions: workspaceDirectory.workspaceTypeOptions,
  currencyOptions: workspaceDirectory.currencyOptions,
  lifecycleImpact: {
    financialHistoryPreserved: true,
    currentSessionCount: 2,
    pendingInvitationCount: 1,
    activeIntegrationConnectionCount: 1,
    activeChatIdentityBindingCount: 2,
  },
};

export const workspaceMembers: WorkspaceMembersDto = {
  workspaceId: session.workspace.id,
  capabilities: { canManageMembers: true },
  items: [
    {
      id: "6db0dc78-6f65-45d8-91d9-ae2575102791",
      userId: session.user.id,
      name: session.user.name,
      email: session.user.email,
      role: "owner",
      status: "active",
      joinedAt: updatedAt,
      updatedAt,
      isSelf: true,
      capabilities: {
        canUpdateRole: false,
        canDisable: false,
        canReactivate: false,
        canTransferOwnership: false,
        canLeave: false,
        assignableRoles: [],
      },
      blockingReasonCodes: ["member_self", "member_owner"],
    },
    {
      id: "b8fd3880-aa65-4b2e-9914-8c2036cf76ac",
      userId: "521c6489-65db-481e-99d6-8a10c0c6f11b",
      name: "Анна",
      email: "anna@example.test",
      role: "editor",
      status: "active",
      joinedAt: updatedAt,
      updatedAt,
      isSelf: false,
      capabilities: {
        canUpdateRole: true,
        canDisable: true,
        canReactivate: false,
        canTransferOwnership: true,
        canLeave: false,
        assignableRoles: ["admin", "editor", "viewer", "uploader", "analyst"],
      },
      blockingReasonCodes: [],
    },
  ],
};

export const workspaceInvitations: WorkspaceInvitationsDto = {
  workspaceId: session.workspace.id,
  capabilities: {
    canCreate: true,
    assignableRoles: ["admin", "editor", "viewer", "uploader", "analyst"],
  },
  items: [
    {
      id: "77893ce6-8de0-46ca-93de-dc0ebc85c755",
      inviteeEmail: "invitee@example.test",
      role: "viewer",
      status: "pending",
      createdAt: updatedAt,
      expiresAt: "2026-08-06T08:30:00Z",
      updatedAt,
      capabilities: { canRevoke: true },
      blockingReasonCodes: [],
    },
  ],
};

export const workspaceActivity: WorkspaceActivityDto = {
  workspaceId: session.workspace.id,
  items: [
    {
      id: "d37da8b5-6a8e-4e51-bcea-e97822bf5212",
      eventType: "member_role_changed",
      actor: { id: session.user.id, displayName: "Max" },
      target: {
        id: "521c6489-65db-481e-99d6-8a10c0c6f11b",
        displayName: "Анна",
      },
      summaryCode: "member_role_changed",
      details: {
        role: null,
        inviteeEmail: null,
        oldRole: "viewer",
        newRole: "editor",
        oldStatus: null,
        newStatus: null,
        oldName: null,
        newName: null,
        oldType: null,
        newType: null,
        oldDefaultCurrency: null,
        newDefaultCurrency: null,
        movedSessionCount: null,
        revokedInvitationCount: null,
      },
      createdAt: updatedAt,
    },
  ],
  nextCursor: null,
};
