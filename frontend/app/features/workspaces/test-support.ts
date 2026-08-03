import type { SessionDto } from "../../api/session";
import type { WorkspaceDirectoryDto } from "./api/workspaces-api";
import type { WorkspaceSettingsDto } from "./api/workspace-settings-api";

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
    canManageMembers: true,
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
      canManageMembers: true,
      canInvite: true,
      canDeactivate: false,
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
