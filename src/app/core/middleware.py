from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from app.core.settings import Settings

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

CallNext = Callable[[Request], Awaitable[Response]]


def install_security_middleware(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    if settings.security_headers_enabled:

        @app.middleware("http")
        async def add_security_headers(request: Request, call_next: CallNext) -> Response:
            response = await call_next(request)
            for name, value in SECURITY_HEADERS.items():
                response.headers.setdefault(name, value)
            if settings.session_cookie_secure:
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )
            return response
