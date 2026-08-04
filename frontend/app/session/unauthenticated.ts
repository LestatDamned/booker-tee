type BrowserLocation = Pick<
  Location,
  "assign" | "hash" | "pathname" | "search"
>;

type StatusResult = { status: string };

export function loginHref(next: string): string {
  return `/app/auth/login?next=${encodeURIComponent(next)}`;
}

export function loginHrefForLocation(
  location: Pick<BrowserLocation, "hash" | "pathname" | "search">,
): string {
  const next = `${location.pathname}${location.search}${location.hash}`;
  return loginHref(next);
}

export function redirectIfUnauthenticated(
  result: StatusResult,
  location: BrowserLocation = window.location,
): result is { status: "unauthenticated" } {
  if (result.status !== "unauthenticated") return false;
  location.assign(loginHrefForLocation(location));
  return true;
}
