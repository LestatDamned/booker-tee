import { index, route, type RouteConfig } from "@react-router/dev/routes";

export default [
  index("routes/home.tsx"),
  route("accounts", "routes/accounts.tsx"),
  route("accounts/:accountId", "routes/account-detail.tsx"),
  route("categories", "routes/categories.tsx"),
  route("categories/:categoryId", "routes/category-detail.tsx"),
  route("foundation", "routes/foundation.tsx"),
  route("imports", "routes/import-documents.tsx"),
  route("imports/upload", "routes/import-upload.tsx"),
  route("imports/documents/:documentId", "routes/import-document-detail.tsx"),
  route("imports/documents/:documentId/mapping", "routes/import-mapping.tsx"),
  route("imports/documents/:documentId/review", "routes/import-review.tsx"),
  route("ledger/manual", "routes/manual-ledger.tsx"),
  route("properties", "routes/properties.tsx"),
  route("reports", "routes/reports.tsx"),
] satisfies RouteConfig;
