import { replace } from "react-router";

import type { Route } from "./+types/manual-ledger";

export function meta() {
  return [{ title: "Операции — Booker Tee" }];
}

export function clientLoader({ request }: Route.ClientLoaderArgs) {
  return replace(`/operations${new URL(request.url).search}`);
}
