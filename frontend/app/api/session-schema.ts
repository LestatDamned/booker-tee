import { z } from "zod";

import type { SessionDto } from "./session";

export const sessionSchema: z.ZodType<SessionDto> = z.object({
  user: z.object({
    id: z.uuid(),
    email: z.email(),
    name: z.string().nullable(),
  }),
  workspace: z.object({
    id: z.uuid(),
    name: z.string(),
    type: z.enum([
      "personal",
      "family",
      "business",
      "property_management",
      "project",
      "other",
    ]),
    defaultCurrency: z.string(),
  }),
  membership: z.object({
    role: z.enum(["owner", "admin", "editor", "viewer", "uploader", "analyst"]),
    status: z.enum(["pending", "active", "disabled", "removed"]),
  }),
  capabilities: z.object({
    canReadWorkspace: z.boolean(),
    canWriteFinancialData: z.boolean(),
    canManageImports: z.boolean(),
    canManageMembers: z.boolean(),
    canManageWorkspace: z.boolean(),
  }),
  csrfToken: z.string(),
});
