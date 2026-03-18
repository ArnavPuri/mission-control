from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import MarketingSignal, MarketingContent, SignalStatus, ContentStatus

router = APIRouter()


@router.get("")
async def marketing_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate stats for the marketing dashboard."""
    # Signal counts by status
    signal_status_counts = {}
    for status in SignalStatus:
        count = await db.scalar(
            select(func.count(MarketingSignal.id)).where(MarketingSignal.status == status)
        )
        signal_status_counts[status.value] = count or 0

    # Signal counts by type
    signal_type_counts = {}
    for signal_type in ["opportunity", "competitor", "feedback", "trend"]:
        count = await db.scalar(
            select(func.count(MarketingSignal.id)).where(MarketingSignal.signal_type == signal_type)
        )
        signal_type_counts[signal_type] = count or 0

    # Content counts by status
    content_status_counts = {}
    for status in ContentStatus:
        count = await db.scalar(
            select(func.count(MarketingContent.id)).where(MarketingContent.status == status)
        )
        content_status_counts[status.value] = count or 0

    # Content counts by channel
    content_channel_result = await db.execute(
        select(MarketingContent.channel, func.count(MarketingContent.id))
        .group_by(MarketingContent.channel)
    )
    content_channel_counts = {row[0]: row[1] for row in content_channel_result.all()}

    return {
        "signals": {
            "by_status": signal_status_counts,
            "by_type": signal_type_counts,
            "total": sum(signal_status_counts.values()),
        },
        "content": {
            "by_status": content_status_counts,
            "by_channel": content_channel_counts,
            "total": sum(content_status_counts.values()),
        },
    }
