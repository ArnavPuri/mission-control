"""API Rate Limiting and Usage Tracking.

In-memory sliding window rate limiter with per-key and global limits.
Tracks API usage statistics for monitoring and billing.
"""

import time
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.api_keys import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# --- In-Memory Rate Limiter ---

class SlidingWindowLimiter:
    """Sliding window rate limiter with per-key tracking."""

    def __init__(self, default_rpm: int = 60, default_rph: int = 1000):
        self.default_rpm = default_rpm  # requests per minute
        self.default_rph = default_rph  # requests per hour
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._usage: dict[str, dict] = defaultdict(lambda: {
            "total_requests": 0,
            "first_seen": None,
            "last_seen": None,
            "endpoints": defaultdict(int),
        })

    def check(self, key: str, rpm: int | None = None, rph: int | None = None) -> tuple[bool, dict]:
        """Check if a request is allowed.

        Returns (allowed, info) where info contains rate limit headers.
        """
        now = time.monotonic()
        rpm = rpm or self.default_rpm
        rph = rph or self.default_rph

        # Clean old entries
        window_requests = self._requests[key]
        minute_ago = now - 60
        hour_ago = now - 3600
        self._requests[key] = [t for t in window_requests if t > hour_ago]

        # Count requests in windows
        minute_count = sum(1 for t in self._requests[key] if t > minute_ago)
        hour_count = len(self._requests[key])

        info = {
            "limit_rpm": rpm,
            "limit_rph": rph,
            "remaining_rpm": max(0, rpm - minute_count),
            "remaining_rph": max(0, rph - hour_count),
            "used_rpm": minute_count,
            "used_rph": hour_count,
        }

        if minute_count >= rpm:
            info["retry_after"] = 60
            return False, info
        if hour_count >= rph:
            info["retry_after"] = 3600
            return False, info

        # Record request
        self._requests[key].append(now)
        return True, info

    def track_usage(self, key: str, endpoint: str):
        """Track API usage for analytics."""
        usage = self._usage[key]
        usage["total_requests"] += 1
        now = datetime.now(timezone.utc).isoformat()
        if not usage["first_seen"]:
            usage["first_seen"] = now
        usage["last_seen"] = now
        usage["endpoints"][endpoint] += 1

    def get_usage(self, key: str | None = None) -> dict:
        """Get usage statistics."""
        if key:
            usage = self._usage.get(key)
            if not usage:
                return {"key": key, "total_requests": 0}
            return {
                "key": key,
                "total_requests": usage["total_requests"],
                "first_seen": usage["first_seen"],
                "last_seen": usage["last_seen"],
                "top_endpoints": dict(
                    sorted(usage["endpoints"].items(), key=lambda x: x[1], reverse=True)[:10]
                ),
            }
        # All keys
        return {
            "total_keys": len(self._usage),
            "total_requests": sum(u["total_requests"] for u in self._usage.values()),
            "keys": {
                k: {
                    "total_requests": v["total_requests"],
                    "last_seen": v["last_seen"],
                }
                for k, v in sorted(
                    self._usage.items(),
                    key=lambda x: x[1]["total_requests"],
                    reverse=True,
                )[:20]
            },
        }

    def reset(self, key: str | None = None):
        """Reset rate limit counters."""
        if key:
            self._requests.pop(key, None)
        else:
            self._requests.clear()


# Global limiter instance
limiter = SlidingWindowLimiter()


# --- Middleware ---

class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that applies rate limiting to API requests."""

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit /api/ routes
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Skip health checks
        if request.url.path in ("/health", "/api/health", "/api/health/detailed"):
            return await call_next(request)

        # Determine key: API key header or IP address
        api_key = request.headers.get("x-api-key", "")
        key = f"apikey:{api_key[:8]}" if api_key else f"ip:{request.client.host}" if request.client else "unknown"

        # Check rate limit
        allowed, info = limiter.check(key)

        if not allowed:
            response = Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )
            response.headers["X-RateLimit-Limit"] = str(info["limit_rpm"])
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["Retry-After"] = str(info.get("retry_after", 60))
            return response

        # Track usage
        limiter.track_usage(key, request.url.path)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(info["limit_rpm"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining_rpm"])

        return response


# --- API Endpoints ---

@router.get("/usage")
async def get_usage_stats(key: str | None = None):
    """Get API usage statistics.

    Without key parameter: returns aggregate stats for all keys.
    With key parameter: returns detailed stats for a specific key.
    """
    return limiter.get_usage(key)


@router.get("/limits")
async def get_rate_limits():
    """Get current rate limit configuration."""
    return {
        "default_rpm": limiter.default_rpm,
        "default_rph": limiter.default_rph,
        "description": "Sliding window rate limiting per API key or IP address",
    }


@router.post("/reset", dependencies=[Depends(require_admin)])
async def reset_rate_limit(key: str | None = None):
    """Reset rate limit counters for a specific key or all keys.

    WARNING: This endpoint has no authentication. In production,
    gate this behind admin auth or remove it entirely.
    """
    logger.warning(f"Rate limit reset requested for key={key or 'ALL'}")
    limiter.reset(key)
    return {"reset": True, "key": key or "all"}
