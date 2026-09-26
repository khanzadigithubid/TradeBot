"""
API Authentication
Shared-secret guard for the endpoints that can move money or change
configuration.

Design notes:
  * Secure by default. The control endpoints used to be open whenever
    `API_SECRET` was unset, with only a startup warning. A public deployment
    (the Render URL is world-reachable) then let anyone overwrite the Binance
    API key, rewrite every strategy parameter, and start or stop trading. An
    unset secret now *closes* those endpoints instead of trusting the operator
    to have noticed the warning.
  * Three states, reported by `control_access_mode()` so the startup banner,
    /api/status and the UI can all say which one is live:
      - "secret"  API_SECRET is set, the X-API-Secret header is required
      - "denied"  no API_SECRET and no opt-out: control endpoints return 503
      - "open"    ALLOW_UNAUTHENTICATED_CONTROL=true, for local dev only
  * Read-only market data, status and the WebSocket stay public so a monitoring
    dashboard keeps working without a secret.
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


def unauthenticated_control_allowed() -> bool:
    """
    Escape hatch for local development only. Without it an unset API_SECRET
    means the control endpoints are closed, not open.
    """
    return (os.getenv("ALLOW_UNAUTHENTICATED_CONTROL") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def control_access_mode() -> str:
    """One of "secret", "denied", "open" — the single source of truth."""
    if auth_enabled():
        return "secret"
    if unauthenticated_control_allowed():
        return "open"
    return "denied"


def control_access_detail() -> str:
    """Operator-facing explanation of the current state."""
    mode = control_access_mode()
    if mode == "secret":
        return "API auth: ENABLED — X-API-Secret is required for control endpoints."
    if mode == "open":
        return (
            "API auth: DISABLED — control endpoints are open to anyone. "
            "ALLOW_UNAUTHENTICATED_CONTROL is set, so never do this on a "
            "public host."
        )
    return (
        "API auth: CLOSED — API_SECRET is not set, so /api/bot/*, "
        "/api/settings and /api/trades/manual return 503 and the dashboard is "
        "read-only. Set API_SECRET in the environment (and VITE_API_SECRET in "
        "the frontend) to re-enable them. Local development can opt out with "
        "ALLOW_UNAUTHENTICATED_CONTROL=true."
    )


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
    wrong, and 503 when no secret is configured at all. No-op when the local
    development opt-out is set.
    """
    mode = control_access_mode()
    if mode == "open":
        return
    if mode == "denied":
        raise HTTPException(503, control_access_detail())

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
    Middleware-friendly auth check. Returns a response when the request must be
    rejected, or None to let it through.

    Middleware must *return* a response: raising HTTPException from inside
    `@app.middleware("http")` escapes the exception handlers and turns every
    unauthenticated call into a 500 crash.
    """
    if not is_protected(request.url.path, request.method):
        return None

    mode = control_access_mode()
    if mode == "open":
        return None

    if mode == "denied":
        logger.warning(
            f"Blocked {request.method} {request.url.path} — API_SECRET is not set"
        )
        return JSONResponse(status_code=503, content={"detail": control_access_detail()})

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
