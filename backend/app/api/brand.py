from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import BrandProfile

router = APIRouter()

DEFAULT_NOTIFICATION_PREFS = {
    "agent_completions": True,
    "agent_failures": True,
    "signal_summary": True,
    "content_drafts": True,
}


class BrandProfileUpdate(BaseModel):
    name: str | None = None
    bio: str | None = None
    tone: str | None = None
    social_handles: dict | None = None
    topics: list[str] | None = None
    talking_points: dict | None = None
    avoid: list[str] | None = None
    example_posts: list[dict] | None = None
    notification_prefs: dict | None = None


class NotificationPrefsUpdate(BaseModel):
    agent_completions: bool | None = None
    agent_failures: bool | None = None
    signal_summary: bool | None = None
    content_drafts: bool | None = None


def _serialize(profile: BrandProfile) -> dict:
    return {
        "id": str(profile.id),
        "name": profile.name,
        "bio": profile.bio,
        "tone": profile.tone,
        "social_handles": profile.social_handles or {},
        "topics": profile.topics or [],
        "talking_points": profile.talking_points or {},
        "avoid": profile.avoid or [],
        "example_posts": profile.example_posts or [],
        "notification_prefs": profile.notification_prefs or DEFAULT_NOTIFICATION_PREFS,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


EMPTY_PROFILE = {
    "id": None,
    "name": "",
    "bio": "",
    "tone": "",
    "social_handles": {},
    "topics": [],
    "talking_points": {},
    "avoid": [],
    "example_posts": [],
    "notification_prefs": DEFAULT_NOTIFICATION_PREFS,
    "created_at": None,
    "updated_at": None,
}


@router.get("")
async def get_brand_profile(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BrandProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        return EMPTY_PROFILE
    return _serialize(profile)


@router.put("")
async def upsert_brand_profile(data: BrandProfileUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BrandProfile).limit(1))
    profile = result.scalar_one_or_none()

    fields = data.model_dump(exclude_unset=True)

    if profile:
        for key, val in fields.items():
            setattr(profile, key, val)
    else:
        profile = BrandProfile(**fields)
        db.add(profile)

    await db.flush()
    return _serialize(profile)


@router.get("/notification-prefs")
async def get_notification_prefs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BrandProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        return DEFAULT_NOTIFICATION_PREFS
    return profile.notification_prefs or DEFAULT_NOTIFICATION_PREFS


@router.put("/notification-prefs")
async def update_notification_prefs(data: NotificationPrefsUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BrandProfile).limit(1))
    profile = result.scalar_one_or_none()

    if not profile:
        profile = BrandProfile(notification_prefs=DEFAULT_NOTIFICATION_PREFS)
        db.add(profile)

    current = profile.notification_prefs or DEFAULT_NOTIFICATION_PREFS
    updates = data.model_dump(exclude_unset=True)
    merged = {**current, **updates}
    profile.notification_prefs = merged

    await db.flush()
    return merged


async def get_notification_prefs_dict(db: AsyncSession) -> dict:
    """Helper for runner to check prefs. Returns defaults if no profile exists."""
    result = await db.execute(select(BrandProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        return DEFAULT_NOTIFICATION_PREFS
    return profile.notification_prefs or DEFAULT_NOTIFICATION_PREFS
