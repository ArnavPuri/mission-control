import hashlib
import secrets
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import ApiKey

router = APIRouter()

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _generate_key() -> str:
    return f"mc_{secrets.token_urlsafe(32)}"


class ApiKeyCreate(BaseModel):
    name: str
    scopes: list[str] = ["read"]
    expires_at: str | None = None


class ApiKeyUpdate(BaseModel):
    name: str | None = None
    scopes: list[str] | None = None
    is_active: bool | None = None


async def verify_api_key(
    api_key: str | None = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> ApiKey | None:
    """Verify an API key and return the ApiKey record. Returns None if no key provided."""
    if not api_key:
        return None

    key_hash = _hash_key(api_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if record.expires_at and record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API key expired")

    # Update last used
    record.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    return record


def require_scope(scope: str):
    """Dependency that checks if the API key has a required scope."""
    async def checker(key: ApiKey | None = Depends(verify_api_key)):
        if key is None:
            return  # No API key auth, allow (internal access)
        if scope not in (key.scopes or []) and "admin" not in (key.scopes or []):
            raise HTTPException(status_code=403, detail=f"API key missing scope: {scope}")
        return key
    return checker


async def require_admin(key: ApiKey | None = Depends(verify_api_key)):
    """Strict auth dependency for sensitive endpoints.

    Requires a valid API key with 'admin' scope. Unlike require_scope(),
    this NEVER falls through — no key = 401.
    """
    if key is None:
        raise HTTPException(
            status_code=401,
            detail="Admin API key required. Pass X-API-Key header.",
        )
    if "admin" not in (key.scopes or []):
        raise HTTPException(status_code=403, detail="Admin scope required")
    return key


@router.get("", dependencies=[Depends(require_scope("admin"))])
async def list_api_keys(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    keys = result.scalars().all()
    return [
        {
            "id": str(k.id),
            "name": k.name,
            "key_prefix": k.key_prefix,
            "scopes": k.scopes or [],
            "is_active": k.is_active,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "expires_at": k.expires_at.isoformat() if k.expires_at else None,
            "created_at": k.created_at.isoformat(),
        }
        for k in keys
    ]


@router.post("", dependencies=[Depends(require_scope("admin"))])
async def create_api_key(data: ApiKeyCreate, db: AsyncSession = Depends(get_db)):
    raw_key = _generate_key()
    key_hash = _hash_key(raw_key)

    expires = None
    if data.expires_at:
        expires = datetime.fromisoformat(data.expires_at)

    record = ApiKey(
        name=data.name,
        key_hash=key_hash,
        key_prefix=raw_key[:8],
        scopes=data.scopes,
        expires_at=expires,
    )
    db.add(record)
    await db.flush()

    # Return the raw key ONLY on creation (never stored)
    return {
        "id": str(record.id),
        "name": record.name,
        "key": raw_key,
        "key_prefix": record.key_prefix,
        "scopes": record.scopes,
        "message": "Save this key now — it won't be shown again.",
    }


@router.patch("/{key_id}", dependencies=[Depends(require_scope("admin"))])
async def update_api_key(key_id: UUID, data: ApiKeyUpdate, db: AsyncSession = Depends(get_db)):
    record = await db.get(ApiKey, key_id)
    if not record:
        raise HTTPException(status_code=404, detail="API key not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(record, key, val)
    await db.flush()
    return {"id": str(record.id), "updated": True}


@router.delete("/{key_id}", dependencies=[Depends(require_scope("admin"))])
async def revoke_api_key(key_id: UUID, db: AsyncSession = Depends(get_db)):
    record = await db.get(ApiKey, key_id)
    if not record:
        raise HTTPException(status_code=404, detail="API key not found")
    record.is_active = False
    await db.flush()
    return {"id": str(record.id), "revoked": True}
