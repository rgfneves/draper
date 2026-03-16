from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def discover(
    platform: str,
    limit: int,
    dry_run: bool = False,
    conn=None,
    seed_ids=None,
) -> list[dict]:
    """
    Fetches usernames using seeds stored in the search_configs DB table.
    Returns list of dicts: {"username": str, "search_type": str, "seed_value": str}
    If dry_run=True, logs what would be done and returns [].
    If seed_ids is provided, only the seeds with those IDs are used.
    """
    from db.connection import get_connection
    from db.repository import get_search_configs

    _conn = conn or get_connection()
    configs = get_search_configs(_conn, platform=platform, active_only=True)

    if seed_ids:
        configs = [c for c in configs if c["id"] in seed_ids]
        logger.info("Filtered to %d seeds by seed_ids=%s", len(configs), seed_ids)

    hashtags = [c["value"] for c in configs if c["search_type"] == "hashtag"]

    if dry_run:
        logger.info(
            "[DRY RUN] platform=%s seeds=%d limit=%d",
            platform, len(configs), limit,
        )
        return []

    if not configs:
        logger.warning("No active search configs for platform=%s. Add seeds in the dashboard.", platform)
        return []

    # Each platform function now returns [(username, search_type, seed_value), ...]
    if platform == "instagram":
        from platforms.instagram import discover_usernames
        locations = [c["value"] for c in configs if c["search_type"] == "location"]
        logger.info("Instagram discovery: %d hashtags, %d locations, limit=%d", len(hashtags), len(locations), limit)
        pairs = discover_usernames(hashtags, locations=locations, limit=limit)

    elif platform == "tiktok":
        from platforms.tiktok import discover_usernames
        keyword_searches = [c["value"] for c in configs if c["search_type"] == "keyword_search"]
        country_codes = [c["value"] for c in configs if c["search_type"] == "country_code"]
        logger.info(
            "TikTok discovery: %d hashtags, %d keywords, %d countries, limit=%d",
            len(hashtags), len(keyword_searches), len(country_codes), limit,
        )
        pairs = discover_usernames(hashtags, keyword_searches, country_codes=country_codes, limit=limit)

    else:
        raise ValueError(f"Unknown platform: {platform!r}")

    # Deduplicate (platform functions already deduplicate, but guard here too)
    seen: set[str] = set()
    result: list[dict] = []
    for username, search_type, seed_value in pairs:
        u = username.lower()
        if u not in seen:
            seen.add(u)
            result.append({"username": u, "search_type": search_type, "seed_value": seed_value})

    result = result[:limit]
    logger.info("Discovery complete: %d unique usernames for %s", len(result), platform)
    return result
