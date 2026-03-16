from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from db.models import Creator, Post
from platforms.apify_client import run_actor

logger = logging.getLogger(__name__)

# Hashtag + video search (returns videos, extract author from authorMeta)
ACTOR_VIDEO_SCRAPER = "clockworks~tiktok-scraper"
# Keyword → user profiles directly (more targeted for influencer discovery)
ACTOR_USER_SEARCH = "clockworks~tiktok-user-search-scraper"


ACTOR_COUNTRY_SCRAPER = "apidojo~tiktok-scraper"


def discover_usernames(
    hashtags: list[str],
    keyword_searches: list[str],
    country_codes: list[str] | None = None,
    limit: int = 500,
) -> list[tuple[str, str, str]]:
    """
    Fetches unique TikTok usernames from three methods.
    Returns [(username, search_type, seed_value), ...] — first seed that found each user wins.
    - hashtags: ACTOR_VIDEO_SCRAPER — extracts author from video data
    - keyword_searches: ACTOR_USER_SEARCH — returns profiles directly
    - country_codes: ACTOR_COUNTRY_SCRAPER — filters by creator country (ISO 2-letter codes)
      applied on top of active hashtags, not standalone
    """
    seen: set[str] = set()
    result: list[tuple[str, str, str]] = []
    total_sources = len(hashtags) + len(keyword_searches)
    per_source = max(1, limit // total_sources) if total_sources else limit

    # --- Hashtag method ---
    for tag in hashtags:
        if len(result) >= limit:
            break
        logger.info("TikTok hashtag discovery: #%s (limit=%d)", tag, per_source)
        try:
            items, _ = run_actor(ACTOR_VIDEO_SCRAPER, {"hashtags": [tag], "resultsPerPage": per_source})
            for item in items:
                author = item.get("authorMeta") or {}
                username = author.get("name") or author.get("uniqueId") or item.get("author")
                if username:
                    u = username.lower()
                    if u not in seen:
                        seen.add(u)
                        result.append((u, "hashtag", tag))
        except Exception as exc:
            logger.warning("TikTok hashtag discovery failed for #%s: %s", tag, exc)

    # --- Keyword search method (returns user profiles directly) ---
    for kw in keyword_searches:
        if len(result) >= limit:
            break
        logger.info("TikTok keyword search: '%s' (limit=%d)", kw, per_source)
        try:
            items, _ = run_actor(ACTOR_USER_SEARCH, {"searchQueries": [kw], "maxItems": per_source})
            for item in items:
                username = (
                    item.get("uniqueId")
                    or item.get("name")
                    or (item.get("authorMeta") or {}).get("name")
                )
                if username:
                    u = username.lower()
                    if u not in seen:
                        seen.add(u)
                        result.append((u, "keyword_search", kw))
        except Exception as exc:
            logger.warning("TikTok keyword search failed for '%s': %s", kw, exc)

    # --- Country filter: hashtag + country code (apidojo actor) ---
    for code in (country_codes or []):
        if len(result) >= limit:
            break
        if not hashtags:
            logger.warning("TikTok country filter '%s' skipped — no active hashtags to combine with.", code)
            continue
        logger.info("TikTok country filter: %s + %d hashtags (limit=%d)", code, len(hashtags), per_source)
        try:
            items, _ = run_actor(
                ACTOR_COUNTRY_SCRAPER,
                {"hashtags": hashtags, "countryCode": code, "maxItems": per_source},
            )
            for item in items:
                author = item.get("authorMeta") or {}
                username = author.get("name") or author.get("uniqueId") or item.get("author")
                if username:
                    u = username.lower()
                    if u not in seen:
                        seen.add(u)
                        result.append((u, "country_code", code))
        except Exception as exc:
            logger.warning("TikTok country filter failed for %s: %s", code, exc)

    result = result[:limit]
    logger.info(
        "TikTok discovery: %d unique usernames (hashtags=%d, keywords=%d, countries=%d)",
        len(result), len(hashtags), len(keyword_searches), len(country_codes or []),
    )
    return result


def scrape_profiles_and_videos(
    usernames: list[str],
    results_per_page: int = 20,
) -> tuple[list[dict], list[dict], float]:
    """
    Scrapes TikTok user videos (which contain profile info).
    Returns (profiles_raw, videos_raw, cost_usd).
    """
    if not usernames:
        return [], [], 0.0
    logger.info("Scraping TikTok videos for %d users", len(usernames))
    items, meta = run_actor(
        ACTOR_VIDEO_SCRAPER,
        {"profiles": usernames, "resultsPerPage": results_per_page},
    )

    by_author: dict[str, list[dict]] = {}
    for item in items:
        author = (item.get("authorMeta") or {}).get("name") or ""
        if author:
            by_author.setdefault(author.lower(), []).append(item)

    videos: list[dict] = items
    profiles: list[dict] = []
    for author_name, author_videos in by_author.items():
        # Use first video to synthesize a profile entry
        profiles.append({"_username": author_name, "_videos": author_videos})

    return profiles, videos, meta.get("cost_usd", 0.0)


def normalize_profile(raw_videos: list[dict]) -> Creator:
    """
    Infers Creator profile from a list of TikTok video dicts.
    Uses first video's authorMeta for profile-level fields.
    """
    if not raw_videos:
        return Creator(platform="tiktok")

    first = raw_videos[0]
    author = first.get("authorMeta") or {}

    username = (author.get("name") or author.get("uniqueId") or "").lower()
    display_name = author.get("nickName") or author.get("disp_name") or username
    fans = author.get("fans") or author.get("followersCount") or 0
    following = author.get("following") or 0
    bio = author.get("signature") or author.get("bio") or ""
    verified = bool(author.get("verified"))
    total_videos = author.get("video") or author.get("videoCount") or 0

    return Creator(
        platform="tiktok",
        username=username,
        display_name=display_name,
        bio=bio,
        followers=fans,
        following=following,
        total_posts=total_videos,
        verified=verified,
        business_account=False,
        is_private=bool(author.get("privateAccount") or author.get("secret")),
        profile_pic_url=author.get("avatar") or author.get("avatarUrl") or author.get("avatarThumb"),
        status="discovered",
    )


def calculate_engagement(
    likes: int,
    comments: int,
    shares: int,
    plays: int,
) -> float:
    """(likes + comments + shares) / plays if plays > 0"""
    likes = likes or 0
    comments = comments or 0
    shares = shares or 0
    plays = plays or 0
    if plays > 0:
        return (likes + comments + shares) / plays
    return 0.0


def normalize_post(raw: dict, creator_id: int) -> Post:
    """Maps Apify TikTok video dict to Post dataclass."""
    likes = raw.get("diggCount") or raw.get("likes") or 0
    comments = raw.get("commentCount") or raw.get("comments") or 0
    shares = raw.get("shareCount") or raw.get("shares") or 0
    plays = raw.get("playCount") or raw.get("plays") or 0

    engagement = calculate_engagement(likes, comments, shares, plays)

    hashtags_raw = raw.get("hashtags") or []
    if isinstance(hashtags_raw, list):
        # Each item may be a dict with 'name' key or a plain string
        tag_names = [
            (h.get("name") if isinstance(h, dict) else str(h))
            for h in hashtags_raw
        ]
        hashtags_json = json.dumps(tag_names)
    else:
        hashtags_json = json.dumps([])

    create_time = raw.get("createTime") or raw.get("createTimeISO")
    if isinstance(create_time, (int, float)):
        published_at = datetime.fromtimestamp(create_time, tz=timezone.utc).isoformat()
    elif isinstance(create_time, str) and create_time:
        published_at = create_time
    else:
        published_at = None

    video_id = str(raw.get("id") or raw.get("videoId") or "")
    author_name = (raw.get("authorMeta") or {}).get("name") or ""
    post_url = f"https://www.tiktok.com/@{author_name}/video/{video_id}" if video_id and author_name else None

    return Post(
        creator_id=creator_id,
        platform="tiktok",
        post_id=video_id,
        post_type="video",
        post_url=post_url,
        published_at=published_at,
        likes=likes,
        comments=comments,
        shares=shares,
        views=plays,
        engagement_rate=engagement,
        caption=raw.get("text") or raw.get("desc") or "",
        hashtags=hashtags_json,
    )
