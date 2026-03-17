from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.models import Creator

logger = logging.getLogger(__name__)


def passes_initial_filter(
    creator: "Creator",
    platform: str,
    *,
    min_followers: int | None = None,
    max_followers: int | None = None,
    excluded_keywords: list[str] | None = None,
    exclude_business: bool = False,
    min_total_posts: int = 0,
    min_follower_ratio: float = 0.0,
    require_email: bool = False,
    excluded_categories: list[str] | None = None,
) -> bool:
    """
    Fast pre-filter based on profile data only (no posts needed).
    Optional overrides take precedence over config defaults.
    """
    from config.filters import EXCLUDED_KEYWORDS, INSTAGRAM, TIKTOK

    thresholds = INSTAGRAM if platform == "instagram" else TIKTOK
    min_f = min_followers if min_followers is not None else thresholds.get("min_followers", 0)
    max_f = max_followers if max_followers is not None else thresholds.get("max_followers", float("inf"))
    kw_list = excluded_keywords if excluded_keywords is not None else EXCLUDED_KEYWORDS

    if creator.is_private:
        return False

    if creator.followers is not None:
        if creator.followers < min_f or creator.followers > max_f:
            return False

    bio = (creator.bio or "").lower()
    for kw in kw_list:
        if re.search(r"\b" + re.escape(kw.lower()) + r"\b", bio):
            return False

    if exclude_business and creator.business_account:
        return False

    if min_total_posts > 0 and (creator.total_posts or 0) < min_total_posts:
        return False

    if min_follower_ratio > 0.0:
        following = creator.following or 0
        followers = creator.followers or 0
        if following > 0:
            if (followers / following) < min_follower_ratio:
                return False

    if require_email and not (creator.email or "").strip():
        return False

    if excluded_categories:
        cat = (creator.category or "").lower()
        if any(ec.lower() in cat for ec in excluded_categories if ec.strip()):
            return False

    return True


def apply_initial_filter(
    creators: list["Creator"],
    platform: str,
    *,
    min_followers: int | None = None,
    max_followers: int | None = None,
    excluded_keywords: list[str] | None = None,
    exclude_business: bool = False,
    min_total_posts: int = 0,
    min_follower_ratio: float = 0.0,
    require_email: bool = False,
    excluded_categories: list[str] | None = None,
) -> tuple[list["Creator"], list["Creator"]]:
    """
    Splits creators into (passed, failed) based on profile-only criteria.
    Does NOT write to DB — caller is responsible for persisting status.
    """
    passed: list["Creator"] = []
    failed: list["Creator"] = []
    for c in creators:
        if passes_initial_filter(
            c, platform,
            min_followers=min_followers,
            max_followers=max_followers,
            excluded_keywords=excluded_keywords,
            exclude_business=exclude_business,
            min_total_posts=min_total_posts,
            min_follower_ratio=min_follower_ratio,
            require_email=require_email,
            excluded_categories=excluded_categories,
        ):
            passed.append(c)
        else:
            failed.append(c)
    logger.info(
        "Initial filter [%s]: %d passed / %d failed (total %d)",
        platform, len(passed), len(failed), len(creators),
    )
    return passed, failed
