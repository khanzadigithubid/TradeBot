"""
API Authentication
Optional shared-secret guard for the endpoints that move money or change
configuration.

Design notes:
  * Disabled by default. If `API_SECRET` is not set the endpoints stay open so
    existing deployments (and the live Render/Vercel pair) are not broken by
    the upgrade. A warning is logged at startup when this is the case.
  * When set, a constant-time comparison of the `X-API-Secret` header is
    required. Read-only market data stays public so charts keep working.
"""

import hmac
import logging
import os

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

HEADER_NAME = "X-API-Secret"

# Endpoints that can place orders, move funds, or change credentials/config.
PROTECTED_PATHS = (
    "/api/bot/start",
    "/api/bot/stop",
    "/api/settings",
    "/api/settings/test-connection",
    "/api/settings/test-telegram",
    "/api/settings/test-email",
    "/api/settings/test-resend",
    "/api/settings/test-discord",
    "/api/trades/manual",
)


def api_secret() -> str:
    return (os.getenv("API_SECRET") or "").strip()


def auth_enabled() -> bool:
    return bool(api_secret())


def is_protected(path: str, method: str) -> bool:
    """Only mutating calls on control paths need the secret."""
    path = path.rstrip("/") or "/"
    if path in PROTECTED_PATHS:
        return True
    # Dynamic routes: /api/trades/{id} (DELETE), /api/market/{sym}/signal is public
    if method.upper() == "DELETE" and path.startswith("/api/trades/"):
        return True
    return False


def verify(request: Request) -> None:
    """
    FastAPI dependency. Raises 403 when auth is on and the header is missing or
    wrong. No-op when API_SECRET is unset.
    """
    if not auth_enabled():
        return
    provided = request.headers.get(HEADER_NAME, "")
    if not provided:
        raise HTTPException(
            401,
            f"Missing {HEADER_NAME} header. This API requires an API secret.",
        )
    if not hmac.compare_digest(provided, api_secret()):
        logger.warning(
            f"Rejected {request.method} {request.url.path} — bad API secret"
        )
        raise HTTPException(401, "Invalid API secret.")


def auth_rejection(request: Request) -> JSONResponse | None:
    """
    Middleware-friendly auth check. Returns a 401 response when the request must
    be rejected, or None to let it through.

    Middleware must *return* a response: raising HTTPException from inside
    `@app.middleware("http")` escapes the exception handlers and turns every
    unauthenticated call into a 500 crash.
    """
    if not auth_enabled() or not is_protected(request.url.path, request.method):
        return None

    provided = request.headers.get(HEADER_NAME, "")
    if not provided:
        detail = f"Missing {HEADER_NAME} header. This API requires an API secret."
    elif not hmac.compare_digest(provided, api_secret()):
        logger.warning(
            f"Rejected {request.method} {request.url.path} — bad API secret"
        )
        detail = "Invalid API secret."
    else:
        return None

    return JSONResponse(
        status_code=401,
        content={"detail": detail},
        headers={"WWW-Authenticate": HEADER_NAME},
    )


async def auth_middleware(request: Request, call_next):
    """
    Middleware form, so dynamic paths (DELETE /api/trades/{id}) are covered too.
    """
    rejection = auth_rejection(request)
    if rejection is not None:
        return rejection
    return await call_next(request)
