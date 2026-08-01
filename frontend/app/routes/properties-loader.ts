import { loadSession } from "../api/session";
import { loadProperties } from "../features/properties/api/properties-api";

export async function loadPropertiesRoute(request: Request) {
  const [session, properties] = await Promise.all([
    loadSession(request.signal),
    loadProperties(request.signal),
  ]);
  return { properties, session };
}
