from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from db.models import Creator, Post
from platforms.apify_client import run_actor

logger = logging.getLogger(__name__)

ACTOR_HASHTAG_POSTS = "reGe1ST3OBgYZSsZJ"
ACTOR_PROFILES = "dSCLg0C3YEZ83HzYX"
ACTOR_POST_DETAILS = "RB9HEZitC8hIUXAha"
ACTOR_LOCATION = "apidojo~instagram-location-scraper"


def discover_usernames(
    hashtags: list[str],
    locations: list[str] | None = None,
    limit: int = 500,
) -> list[tuple[str, str, str]]:
    """
    Scrapes Instagram hashtags and/or locations, extracts unique usernames.
    Returns [(username, search_type, seed_value), ...] — first seed that found each user wins.
    - hashtags: uses ACTOR_HASHTAG_POSTS
    - locations: uses ACTOR_LOCATION (Instagram numeric location IDs → posts tagged there → authors)
    """
    seen: set[str] = set()
    result: list[tuple[str, str, str]] = []
    all_sources = len(hashtags) + len(locations or [])
    per_source = max(1, limit // all_sources) if all_sources else limit

    for tag in hashtags:
        if len(result) >= limit:
            break
        logger.info("Instagram hashtag discovery: #%s (limit=%d)", tag, per_source)
        try:
            items, _ = run_actor(
                ACTOR_HASHTAG_POSTS,
                {"hashtags": [tag], "resultsLimit": per_source},
            )
            for item in items:
                username = item.get("ownerUsername") or item.get("owner", {}).get("username")
                if username:
                    u = username.lower()
                    if u not in seen:
                        seen.add(u)
                        result.append((u, "hashtag", tag))
        except Exception as exc:
            logger.warning("Instagram hashtag discovery failed for #%s: %s", tag, exc)

    for location in (locations or []):
        if len(result) >= limit:
            break
        logger.info("Instagram location discovery: '%s' (limit=%d)", location, per_source)
        try:
            items, _ = run_actor(
                ACTOR_LOCATION,
                {"locationIds": [location], "resultsLimit": per_source},
            )
            for item in items:
                username = (
                    item.get("ownerUsername")
                    or item.get("owner", {}).get("username")
                    or item.get("username")
                )
                if username:
                    u = username.lower()
                    if u not in seen:
                        seen.add(u)
                        result.append((u, "location", location))
        except Exception as exc:
            logger.warning("Instagram location discovery failed for '%s': %s", location, exc)

    result = result[:limit]
    logger.info(
        "Instagram discovery: %d unique usernames (hashtags=%d, locations=%d)",
        len(result), len(hashtags), len(locations or []),
    )
    return result


def scrape_profiles(usernames: list[str]) -> tuple[list[dict], float]:
    """Returns (raw profile dicts, cost_usd)."""
    if not usernames:
        return [], 0.0
    logger.info("Scraping %d Instagram profiles", len(usernames))
    items, meta = run_actor(ACTOR_PROFILES, {"usernames": usernames})
    return items, meta.get("cost_usd", 0.0)


def scrape_posts(usernames: list[str], limit_per_user: int = 30) -> tuple[list[dict], float]:
    """Returns (raw post dicts, cost_usd)."""
    if not usernames:
        return [], 0.0
    logger.info("Scraping Instagram posts for %d users", len(usernames))
    direct_urls = [f"https://www.instagram.com/{u}/" for u in usernames]
    items, meta = run_actor(
        ACTOR_POST_DETAILS,
        {"directUrls": direct_urls, "resultsLimit": limit_per_user},
    )
    return items, meta.get("cost_usd", 0.0)


def classify_post_type(raw: dict) -> str:
    """Returns 'video' | 'image' | 'sidecar'."""
    raw_type = (raw.get("type") or raw.get("productType") or "").lower()
    if raw_type in ("video", "reel", "clips"):
        return "video"
    if raw_type in ("sidecar", "carousel", "carousel_container"):
        return "sidecar"
    if raw.get("videoViewCount") or raw.get("videoPlayCount"):
        return "video"
    if raw.get("childPosts") or raw.get("images"):
        return "sidecar"
    return "image"


def calculate_engagement(
    post_type: str,
    likes: int,
    comments: int,
    views: int,
    followers: int,
) -> float:
    """
    video/reels: (likes + comments) / views if views > 0
    image/sidecar: (likes + comments) / followers if followers > 0
    """
    likes = likes or 0
    comments = comments or 0
    if post_type == "video":
        if views and views > 0:
            return (likes + comments) / views
        return 0.0
    else:
        if followers and followers > 0:
            return (likes + comments) / followers
        return 0.0


def normalize_profile(raw: dict) -> Creator:
    """Maps Apify Instagram profile fields to Creator dataclass."""
    return Creator(
        platform="instagram",
        username=(raw.get("username") or "").lower(),
        display_name=raw.get("fullName") or raw.get("full_name"),
        bio=raw.get("biography") or raw.get("bio") or "",
        link_in_bio=raw.get("externalUrl") or raw.get("external_url"),
        followers=raw.get("followersCount") or raw.get("followers_count") or raw.get("edge_followed_by", {}).get("count"),
        following=raw.get("followingCount") or raw.get("following_count") or raw.get("edge_follow", {}).get("count"),
        total_posts=raw.get("postsCount") or raw.get("posts_count") or raw.get("edge_owner_to_timeline_media", {}).get("count"),
        verified=bool(raw.get("verified") or raw.get("is_verified")),
        business_account=bool(raw.get("isBusinessAccount") or raw.get("is_business_account")),
        is_private=bool(raw.get("isPrivate") or raw.get("is_private")),
        profile_pic_url=raw.get("profilePicUrl") or raw.get("profile_pic_url") or raw.get("profilePicUrlHD"),
        email=raw.get("publicEmail") or raw.get("email") or raw.get("businessEmail"),
        category=raw.get("businessCategoryName") or raw.get("category") or raw.get("categoryName"),
        location=raw.get("city") or raw.get("location") or raw.get("business_address_json"),
        status="discovered",
    )


def normalize_post(raw: dict, creator_id: int) -> Post:
    """Maps Apify Instagram post fields to Post dataclass."""
    post_type = classify_post_type(raw)
    likes = raw.get("likesCount") or raw.get("likes_count") or 0
    comments = raw.get("commentsCount") or raw.get("comments_count") or 0
    views = raw.get("videoViewCount") or raw.get("video_view_count") or raw.get("videoPlayCount") or 0
    followers = raw.get("ownerFollowersCount") or 0

    engagement = calculate_engagement(post_type, likes, comments, views, followers)

    hashtags_raw = raw.get("hashtags") or []
    if isinstance(hashtags_raw, list):
        hashtags_json = json.dumps(hashtags_raw)
    else:
        hashtags_json = json.dumps([])

    timestamp = raw.get("timestamp") or raw.get("taken_at_timestamp")
    if isinstance(timestamp, (int, float)):
        published_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    else:
        published_at = str(timestamp) if timestamp else None

    short_code = raw.get("shortCode") or raw.get("shortcode") or raw.get("code")
    post_url = f"https://www.instagram.com/p/{short_code}/" if short_code else None

    return Post(
        creator_id=creator_id,
        platform="instagram",
        post_id=str(raw.get("id") or short_code or ""),
        post_type=post_type,
        post_url=post_url,
        published_at=published_at,
        likes=likes,
        comments=comments,
        shares=0,
        views=views,
        engagement_rate=engagement,
        caption=raw.get("caption") or "",
        hashtags=hashtags_json,
    )
