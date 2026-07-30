import { index, route, type RouteConfig } from "@react-router/dev/routes";

export default [
  index("routes/home.tsx"),
  route("accounts", "routes/accounts.tsx"),
  route("foundation", "routes/foundation.tsx"),
  route("imports", "routes/import-documents.tsx"),
  route("imports/upload", "routes/import-upload.tsx"),
  route("imports/documents/:documentId", "routes/import-document-detail.tsx"),
  route("imports/documents/:documentId/mapping", "routes/import-mapping.tsx"),
  route("imports/documents/:documentId/review", "routes/import-review.tsx"),
  route("ledger/manual", "routes/manual-ledger.tsx"),
] satisfies RouteConfig;
