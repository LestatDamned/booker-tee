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

export const links: Route.LinksFunction = () => [
  { rel: "stylesheet", href: stylesheet },
];

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
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
  return (
    <main className="centered-state" aria-busy="true">
      <p className="eyebrow">Booker Tee</p>
      <h1>Загружаем workspace…</h1>
    </main>
  );
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  const message = isRouteErrorResponse(error)
    ? `${error.status}: ${error.statusText}`
    : "Не удалось открыть приложение.";

  return (
    <main className="centered-state" role="alert">
      <p className="eyebrow">Booker Tee</p>
      <h1>Что-то пошло не так</h1>
      <p>{message}</p>
      <a className="button-link" href="/app">
        Попробовать снова
      </a>
    </main>
  );
}
