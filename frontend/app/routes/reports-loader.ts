import { loadSession } from "../api/session";
import { loadReportOverview } from "../features/reports/api/reports-api";

export async function loadReportsRoute(request: Request) {
  const url = new URL(request.url);
  const [session, reports] = await Promise.all([
    loadSession(request.signal),
    loadReportOverview(url.search, request.signal),
  ]);
  return { reports, session };
}
