from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_PLATFORM_THRESHOLDS = {
    "instagram": {
        "min_posts_30_days": 4,
    },
    "tiktok": {
        "min_posts_30_days": 4,  # derived from min_posting_frequency 0.14 * 30 ≈ 4.2
    },
}


def _parse_dt(value: Any) -> datetime | None:
    """Parse various datetime representations to a UTC-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str):
        if not value:
            return None
        # Try fromisoformat first (handles +00:00 and .ffffff offsets natively)
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
        # Try stripping trailing Z for UTC
        cleaned = value.rstrip("Z")
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(value).astimezone(timezone.utc)
        except Exception:
            pass
    return None


def analyze_creator(creator: Any, posts: list) -> dict:
    """
    Calculates posting metrics and activity for a creator.

    Returns dict with:
    - avg_engagement
    - posts_last_30_days, posts_last_60_days, posts_last_90_days
    - posting_frequency (posts/day based on last 90 days)
    - aging_breakdown: {'0_30': int, '31_60': int, '61_90': int, 'over_90': int}
    - is_active: bool
    """
    now = datetime.now(tz=timezone.utc)
    cutoff_30 = now - timedelta(days=30)
    cutoff_60 = now - timedelta(days=60)
    cutoff_90 = now - timedelta(days=90)

    aging_breakdown = {"0_30": 0, "31_60": 0, "61_90": 0, "over_90": 0}
    engagement_values: list[float] = []
    posts_last_30 = 0
    posts_last_60 = 0
    posts_last_90 = 0

    for post in posts:
        # Get published_at — support both dataclass and dict
        if hasattr(post, "published_at"):
            raw_dt = post.published_at
        elif isinstance(post, dict):
            raw_dt = post.get("published_at")
        else:
            raw_dt = None

        published_at = _parse_dt(raw_dt)

        # Engagement
        if hasattr(post, "engagement_rate"):
            eng = post.engagement_rate
        elif isinstance(post, dict):
            eng = post.get("engagement_rate")
        else:
            eng = None
        if eng is not None and eng >= 0:
            engagement_values.append(eng)

        if published_at is None:
            aging_breakdown["over_90"] += 1
            continue

        age_days = (now - published_at).total_seconds() / 86400

        if age_days <= 30:
            aging_breakdown["0_30"] += 1
            posts_last_30 += 1
            posts_last_60 += 1
            posts_last_90 += 1
        elif age_days <= 60:
            aging_breakdown["31_60"] += 1
            posts_last_60 += 1
            posts_last_90 += 1
        elif age_days <= 90:
            aging_breakdown["61_90"] += 1
            posts_last_90 += 1
        else:
            aging_breakdown["over_90"] += 1

    avg_engagement = sum(engagement_values) / len(engagement_values) if engagement_values else 0.0
    posting_frequency = posts_last_90 / 90.0

    # Determine is_active using platform thresholds
    platform = getattr(creator, "platform", None) or "instagram"
    thresholds = _PLATFORM_THRESHOLDS.get(platform, _PLATFORM_THRESHOLDS["instagram"])
    is_active = posts_last_30 >= thresholds["min_posts_30_days"]

    return {
        "avg_engagement": avg_engagement,
        "posts_last_30_days": posts_last_30,
        "posts_last_60_days": posts_last_60,
        "posts_last_90_days": posts_last_90,
        "posting_frequency": posting_frequency,
        "aging_breakdown": aging_breakdown,
        "is_active": is_active,
    }


def is_irrelevant_by_keywords(
    bio: str,
    captions: list[str],
    excluded_keywords: list[str],
) -> bool:
    """
    Returns True if bio or any caption contains an excluded keyword as a whole word
    (case-insensitive, word-boundary aware). Prevents false matches like
    'food' inside 'seafood' or 'fashion' inside 'passionate'.
    """
    bio_lower = (bio or "").lower()
    captions_lower = [(c or "").lower() for c in (captions or [])]
    for keyword in excluded_keywords:
        pattern = re.compile(r"\b" + re.escape(keyword.lower()) + r"\b")
        if pattern.search(bio_lower):
            return True
        for caption in captions_lower:
            if pattern.search(caption):
                return True
    return False
