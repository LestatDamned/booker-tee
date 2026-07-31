import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  isRouteErrorResponse,
} from "react-router";

import type { Route } from "./+types/root";
import stylesheet from "./styles/app.css?url";
import { RouteLoadingPage } from "./ui/route-state-page/route-loading-page";
import { RouteStatePage } from "./ui/route-state-page/route-state-page";

export const links: Route.LinksFunction = () => [
  { rel: "stylesheet", href: stylesheet },
];

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html data-theme="catppuccin-mocha" lang="ru">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}

export function HydrateFallback() {
  return <RouteLoadingPage eyebrow="Booker Tee" title="Загружаем workspace…" />;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  const message = isRouteErrorResponse(error)
    ? `${error.status}: ${error.statusText}`
    : "Не удалось открыть приложение.";

  return (
    <RouteStatePage
      actionHref="/app"
      actionLabel="Попробовать снова"
      eyebrow="Booker Tee"
      kind="error"
      title="Что-то пошло не так"
    >
      {message}
    </RouteStatePage>
  );
}
