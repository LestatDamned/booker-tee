import { loadSession } from "../api/session";
import { loadDashboard } from "../features/dashboard/api/dashboard-api";

export async function loadDashboardRoute(request: Request) {
  const [session, dashboard] = await Promise.all([
    loadSession(request.signal),
    loadDashboard(request.signal),
  ]);
  return { dashboard, session };
}
