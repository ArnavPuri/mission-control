"""
Dashboard & API login.

Single user: set DASHBOARD_PASSWORD and the dashboard asks for it once, then
keeps a signed session cookie. Scripts can send `Authorization: Bearer
<API_TOKEN>` instead. With no password set, the API is open (fine on
localhost, and the dashboard shows a warning) — never expose it like that.

Telegram is unaffected: the bot has its own allowlist.
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

COOKIE = "mc_session"
SESSION_DAYS = 30
# Paths that work without logging in
PUBLIC_PATHS = ("/health", "/api/auth/", "/docs", "/openapi.json")

# A few failed logins per IP are fine; more get slowed down
MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 15 * 60
_failures: dict[str, deque] = defaultdict(deque)


def auth_enabled() -> bool:
    return bool(settings.dashboard_password)


def _secret() -> bytes:
    # Derived from the password unless set explicitly, so changing the
    # password signs everyone out
    base = settings.auth_secret or f"mission-control:{settings.dashboard_password}"
    return hashlib.sha256(base.encode()).digest()


def make_session(now: float | None = None) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({
        "exp": int((time.time() if now is None else now) + SESSION_DAYS * 86400),
    }).encode()).decode()
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def valid_session(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    payload, sig = token.rsplit(".", 1)
    expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except ValueError:
        return False
    return data.get("exp", 0) > time.time()


def valid_bearer(header: str | None) -> bool:
    if not settings.api_token or not header or not header.startswith("Bearer "):
        return False
    return hmac.compare_digest(header.removeprefix("Bearer ").strip(), settings.api_token)


def is_authorized(cookies, headers) -> bool:
    if not auth_enabled():
        return True
    return valid_session(cookies.get(COOKIE)) or valid_bearer(headers.get("authorization"))


class AuthMiddleware(BaseHTTPMiddleware):
    """Rejects API requests without a session cookie or API token."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        protected = path.startswith("/api/") and not path.startswith(PUBLIC_PATHS)
        if protected and request.method != "OPTIONS" and not is_authorized(request.cookies, request.headers):
            return JSONResponse({"detail": "Not signed in"}, status_code=401)
        return await call_next(request)


router = APIRouter()


class LoginRequest(BaseModel):
    password: str


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "?")


@router.get("/me")
async def me(request: Request):
    return {
        "auth_enabled": auth_enabled(),
        "authenticated": is_authorized(request.cookies, request.headers),
    }


@router.post("/login")
async def login(data: LoginRequest, request: Request, response: Response):
    if not auth_enabled():
        return {"authenticated": True, "auth_enabled": False}

    ip = _client_ip(request)
    now = time.time()
    recent = _failures[ip]
    while recent and recent[0] < now - FAILURE_WINDOW_SECONDS:
        recent.popleft()
    if len(recent) >= MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")

    if not secrets.compare_digest(data.password.encode(), settings.dashboard_password.encode()):
        recent.append(now)
        logger.warning(f"Failed dashboard login from {ip}")
        raise HTTPException(status_code=401, detail="Wrong password")

    recent.clear()
    response.set_cookie(
        COOKIE, make_session(), max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
    )
    return {"authenticated": True, "auth_enabled": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"authenticated": False}
