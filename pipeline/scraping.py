from __future__ import annotations

import logging

from db.models import Creator, Post

logger = logging.getLogger(__name__)

# How many TikTok videos to fetch in the profile-only phase (just enough for author metadata)
_TIKTOK_PROFILE_PEEK = 2


def scrape_profiles_only(
    platform: str,
    usernames: list[str],
) -> tuple[list[Creator], float]:
    """
    Scrapes profile metadata only (no posts).
    Cheap — used before the initial filter to avoid paying for posts on bad creators.
    Returns (creators, apify_cost_usd).
    """
    if not usernames:
        return [], 0.0

    if platform == "instagram":
        return _profiles_instagram(usernames)
    elif platform == "tiktok":
        return _profiles_tiktok(usernames)
    else:
        raise ValueError(f"Unknown platform: {platform!r}")


def scrape_posts_only(
    platform: str,
    usernames: list[str],
    max_posts: int = 30,
) -> tuple[list[Post], float]:
    """
    Scrapes posts/videos for creators that already passed the initial filter.
    Expensive — only called for the filtered subset.
    Returns (posts, apify_cost_usd).
    """
    if not usernames:
        return [], 0.0

    if platform == "instagram":
        return _posts_instagram(usernames, max_posts=max_posts)
    elif platform == "tiktok":
        return _posts_tiktok(usernames, max_posts=max_posts)
    else:
        raise ValueError(f"Unknown platform: {platform!r}")


# ── Instagram ──────────────────────────────────────────────────────────────────

def _profiles_instagram(usernames: list[str]) -> tuple[list[Creator], float]:
    from platforms.instagram import normalize_profile, scrape_profiles

    raw_profiles, cost = scrape_profiles(usernames)
    creators: list[Creator] = []
    seen: set[str] = set()
    for raw in raw_profiles:
        creator = normalize_profile(raw)
        if creator.username:
            seen.add(creator.username.lower())
            creators.append(creator)

    # Stub any missing so every discovered username gets a DB row
    for username in usernames:
        if username.lower() not in seen:
            creators.append(Creator(platform="instagram", username=username.lower()))

    logger.info("Instagram profile scrape: %d creators (cost $%.4f)", len(creators), cost)
    return creators, cost


def _posts_instagram(usernames: list[str], max_posts: int = 30) -> tuple[list[Post], float]:
    from platforms.instagram import normalize_post, scrape_posts

    raw_posts, cost = scrape_posts(usernames, limit_per_user=max_posts)
    posts: list[Post] = []
    for raw in raw_posts:
        post = normalize_post(raw, creator_id=0)
        post._owner_username = (raw.get("ownerUsername") or "").lower()  # type: ignore[attr-defined]
        posts.append(post)

    logger.info("Instagram post scrape: %d posts for %d users (cost $%.4f)", len(posts), len(usernames), cost)
    return posts, cost


# ── TikTok ─────────────────────────────────────────────────────────────────────

def _profiles_tiktok(usernames: list[str]) -> tuple[list[Creator], float]:
    """
    TikTok profile data lives inside video metadata, so we fetch a tiny number of
    videos (TIKTOK_PROFILE_PEEK) just to extract author fields.
    """
    from platforms.tiktok import normalize_profile, scrape_profiles_and_videos

    raw_profile_stubs, _raw_videos, cost = scrape_profiles_and_videos(
        usernames, results_per_page=_TIKTOK_PROFILE_PEEK
    )
    creators: list[Creator] = []
    seen: set[str] = set()
    for stub in raw_profile_stubs:
        author_videos = stub.get("_videos", [])
        creator = normalize_profile(author_videos)
        if creator.username:
            seen.add(creator.username.lower())
            creators.append(creator)

    for username in usernames:
        if username.lower() not in seen:
            creators.append(Creator(platform="tiktok", username=username.lower()))

    logger.info("TikTok profile scrape: %d creators (cost $%.4f)", len(creators), cost)
    return creators, cost


def _posts_tiktok(usernames: list[str], max_posts: int = 20) -> tuple[list[Post], float]:
    from platforms.tiktok import normalize_post, scrape_profiles_and_videos

    _raw_profile_stubs, raw_videos, cost = scrape_profiles_and_videos(
        usernames, results_per_page=max_posts
    )
    posts: list[Post] = []
    for raw in raw_videos:
        post = normalize_post(raw, creator_id=0)
        author_name = ((raw.get("authorMeta") or {}).get("name") or "").lower()
        post._owner_username = author_name  # type: ignore[attr-defined]
        posts.append(post)

    logger.info("TikTok post scrape: %d videos for %d users (cost $%.4f)", len(posts), len(usernames), cost)
    return posts, cost


# ── Legacy helper (kept for --skip-scrape / analyze-only flows) ────────────────

def fetch_profiles_and_posts(
    platform: str,
    usernames: list[str],
    dry_run: bool = False,
    max_posts: int = 30,
) -> tuple[list[Creator], list[Post], float]:
    """Combined scrape (profiles + posts in one call). Used by legacy code paths."""
    if dry_run:
        logger.info("[DRY RUN] Would scrape %d %s profiles/posts", len(usernames), platform)
        return [], [], 0.0
    if not usernames:
        return [], [], 0.0

    creators, profile_cost = scrape_profiles_only(platform, usernames)
    posts, posts_cost = scrape_posts_only(platform, usernames, max_posts=max_posts)
    return creators, posts, profile_cost + posts_cost
