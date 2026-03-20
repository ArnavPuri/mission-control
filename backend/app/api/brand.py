from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import BrandProfile

router = APIRouter()


class BrandProfileUpdate(BaseModel):
    name: str | None = None
    bio: str | None = None
    tone: str | None = None
    social_handles: dict | None = None
    topics: list[str] | None = None
    talking_points: dict | None = None
    avoid: list[str] | None = None
    example_posts: list[dict] | None = None


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
