from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from db.models import Creator, Post

logger = logging.getLogger(__name__)


def _row_to_creator(row) -> Creator:
    d = dict(row)
    return Creator(**{k: d.get(k) for k in Creator.__dataclass_fields__})


def upsert_creator(conn, creator: Creator) -> int:
    """INSERT OR UPDATE creator record. Returns the creator id."""
    now = datetime.now(timezone.utc).isoformat()
    sql = """
        INSERT INTO creators (
            platform, username, display_name, bio, link_in_bio,
            followers, following, total_posts, verified, business_account,
            is_private, profile_pic_url, email, category,
            location, niche, ai_filter_pass, ai_filter_reason,
            epic_trip_score, score_engagement, score_niche, score_followers,
            score_growth, score_activity, avg_engagement, posts_last_30_days,
            posting_frequency, is_active, discovered_via_type, discovered_via_value,
            status, first_seen_at, last_updated_at
        ) VALUES (
            %(platform)s, %(username)s, %(display_name)s, %(bio)s, %(link_in_bio)s,
            %(followers)s, %(following)s, %(total_posts)s, %(verified)s, %(business_account)s,
            %(is_private)s, %(profile_pic_url)s, %(email)s, %(category)s,
            %(location)s, %(niche)s, %(ai_filter_pass)s, %(ai_filter_reason)s,
            %(epic_trip_score)s, %(score_engagement)s, %(score_niche)s, %(score_followers)s,
            %(score_growth)s, %(score_activity)s, %(avg_engagement)s, %(posts_last_30_days)s,
            %(posting_frequency)s, %(is_active)s, %(discovered_via_type)s, %(discovered_via_value)s,
            %(status)s, %(first_seen_at)s, %(last_updated_at)s
        )
        ON CONFLICT(platform, username) DO UPDATE SET
            display_name        = EXCLUDED.display_name,
            bio                 = EXCLUDED.bio,
            link_in_bio         = EXCLUDED.link_in_bio,
            followers           = EXCLUDED.followers,
            following           = EXCLUDED.following,
            total_posts         = EXCLUDED.total_posts,
            verified            = EXCLUDED.verified,
            business_account    = EXCLUDED.business_account,
            is_private          = EXCLUDED.is_private,
            profile_pic_url     = COALESCE(EXCLUDED.profile_pic_url, creators.profile_pic_url),
            email               = COALESCE(EXCLUDED.email, creators.email),
            category            = COALESCE(EXCLUDED.category, creators.category),
            location            = COALESCE(EXCLUDED.location, creators.location),
            niche               = COALESCE(EXCLUDED.niche, creators.niche),
            ai_filter_pass      = COALESCE(EXCLUDED.ai_filter_pass, creators.ai_filter_pass),
            ai_filter_reason    = COALESCE(EXCLUDED.ai_filter_reason, creators.ai_filter_reason),
            epic_trip_score     = COALESCE(EXCLUDED.epic_trip_score, creators.epic_trip_score),
            score_engagement    = COALESCE(EXCLUDED.score_engagement, creators.score_engagement),
            score_niche         = COALESCE(EXCLUDED.score_niche, creators.score_niche),
            score_followers     = COALESCE(EXCLUDED.score_followers, creators.score_followers),
            score_growth        = COALESCE(EXCLUDED.score_growth, creators.score_growth),
            score_activity      = COALESCE(EXCLUDED.score_activity, creators.score_activity),
            avg_engagement      = COALESCE(EXCLUDED.avg_engagement, creators.avg_engagement),
            posts_last_30_days  = COALESCE(EXCLUDED.posts_last_30_days, creators.posts_last_30_days),
            posting_frequency   = COALESCE(EXCLUDED.posting_frequency, creators.posting_frequency),
            is_active           = COALESCE(EXCLUDED.is_active, creators.is_active),
            discovered_via_type  = COALESCE(creators.discovered_via_type, EXCLUDED.discovered_via_type),
            discovered_via_value = COALESCE(creators.discovered_via_value, EXCLUDED.discovered_via_value),
            status              = CASE
                                    WHEN creators.status IN ('excluded', 'contacted', 'deleted') THEN creators.status
                                    ELSE COALESCE(EXCLUDED.status, creators.status)
                                  END,
            last_updated_at     = %(last_updated_at)s
        RETURNING id
    """
    params = {
        "platform": creator.platform,
        "username": creator.username,
        "display_name": creator.display_name,
        "bio": creator.bio,
        "link_in_bio": creator.link_in_bio,
        "followers": creator.followers,
        "following": creator.following,
        "total_posts": creator.total_posts,
        "verified": creator.verified,
        "business_account": creator.business_account,
        "is_private": creator.is_private,
        "profile_pic_url": creator.profile_pic_url,
        "email": creator.email,
        "category": creator.category,
        "location": creator.location,
        "niche": creator.niche,
        "ai_filter_pass": creator.ai_filter_pass,
        "ai_filter_reason": creator.ai_filter_reason,
        "epic_trip_score": creator.epic_trip_score,
        "score_engagement": creator.score_engagement,
        "score_niche": creator.score_niche,
        "score_followers": creator.score_followers,
        "score_growth": creator.score_growth,
        "score_activity": creator.score_activity,
        "avg_engagement": creator.avg_engagement,
        "posts_last_30_days": creator.posts_last_30_days,
        "posting_frequency": creator.posting_frequency,
        "is_active": creator.is_active,
        "discovered_via_type": creator.discovered_via_type,
        "discovered_via_value": creator.discovered_via_value,
        "status": creator.status,
        "first_seen_at": creator.first_seen_at or now,
        "last_updated_at": now,
    }
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    conn.commit()
    return row["id"]


def upsert_post(conn, post: Post) -> int:
    """INSERT OR UPDATE post record. Returns the post id."""
    sql = """
        INSERT INTO posts (
            creator_id, platform, post_id, post_type, post_url, published_at,
            likes, comments, shares, views, engagement_rate, caption, hashtags
        ) VALUES (
            %(creator_id)s, %(platform)s, %(post_id)s, %(post_type)s, %(post_url)s, %(published_at)s,
            %(likes)s, %(comments)s, %(shares)s, %(views)s, %(engagement_rate)s, %(caption)s, %(hashtags)s
        )
        ON CONFLICT(platform, post_id) DO UPDATE SET
            creator_id      = EXCLUDED.creator_id,
            post_type       = EXCLUDED.post_type,
            post_url        = COALESCE(EXCLUDED.post_url, posts.post_url),
            published_at    = EXCLUDED.published_at,
            likes           = EXCLUDED.likes,
            comments        = EXCLUDED.comments,
            shares          = EXCLUDED.shares,
            views           = EXCLUDED.views,
            engagement_rate = EXCLUDED.engagement_rate,
            caption         = EXCLUDED.caption,
            hashtags        = EXCLUDED.hashtags
        RETURNING id
    """
    params = {
        "creator_id": post.creator_id,
        "platform": post.platform,
        "post_id": post.post_id,
        "post_type": post.post_type,
        "post_url": post.post_url,
        "published_at": post.published_at,
        "likes": post.likes,
        "comments": post.comments,
        "shares": post.shares,
        "views": post.views,
        "engagement_rate": post.engagement_rate,
        "caption": post.caption,
        "hashtags": post.hashtags,
    }
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    conn.commit()
    if row is None:
        raise RuntimeError(f"upsert_post: could not find post after upsert (platform={post.platform} post_id={post.post_id!r})")
    return row["id"]


def get_creator_by_username(conn, platform: str, username: str) -> Creator | None:
    row = conn.execute(
        "SELECT * FROM creators WHERE platform=%s AND username=%s",
        (platform, username),
    ).fetchone()
    if row is None:
        return None
    return _row_to_creator(row)


def get_all_creators(
    conn,
    platform: str | None = None,
    status: str | None = None,
) -> list[Creator]:
    conditions: list[str] = []
    params: list = []
    if platform is not None:
        conditions.append("platform = %s")
        params.append(platform)
    if status is not None:
        conditions.append("status = %s")
        params.append(status)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(f"SELECT * FROM creators {where}", params).fetchall()
    return [_row_to_creator(r) for r in rows]


def update_creator_score(conn, creator_id: int, scores: dict) -> None:
    conn.execute(
        """
        UPDATE creators SET
            epic_trip_score  = %(epic_trip_score)s,
            score_engagement = %(score_engagement)s,
            score_niche      = %(score_niche)s,
            score_followers  = %(score_followers)s,
            score_growth     = %(score_growth)s,
            score_activity   = %(score_activity)s,
            last_updated_at  = %(now)s
        WHERE id = %(id)s
        """,
        {
            "epic_trip_score": scores.get("epic_trip_score"),
            "score_engagement": scores.get("score_engagement"),
            "score_niche": scores.get("score_niche"),
            "score_followers": scores.get("score_followers"),
            "score_growth": scores.get("score_growth"),
            "score_activity": scores.get("score_activity"),
            "now": datetime.now(timezone.utc).isoformat(),
            "id": creator_id,
        },
    )
    conn.commit()


def update_creator_ai_filter(
    conn, creator_id: int, ai_pass: bool, reason: str
) -> None:
    conn.execute(
        """
        UPDATE creators SET
            ai_filter_pass   = %s,
            ai_filter_reason = %s,
            last_updated_at  = %s
        WHERE id = %s
        """,
        (ai_pass, reason, datetime.now(timezone.utc).isoformat(), creator_id),
    )
    conn.commit()


def update_creator_status(conn, creator_id: int, status: str) -> None:
    conn.execute(
        "UPDATE creators SET status=%s, last_updated_at=%s WHERE id=%s",
        (status, datetime.now(timezone.utc).isoformat(), creator_id),
    )
    conn.commit()


def set_creator_lead(conn, creator_ids: list[int], is_lead: bool) -> int:
    """Marks or unmarks creators as a good lead. Independent of status. Returns count updated."""
    if not creator_ids:
        return 0
    placeholders = ",".join(["%s"] * len(creator_ids))
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        f"UPDATE creators SET is_lead=%s, last_updated_at=%s WHERE id IN ({placeholders})",
        [is_lead, now, *creator_ids],
    )
    conn.commit()
    return cur.rowcount


def bulk_update_creator_status(conn, creator_ids: list[int], status: str) -> int:
    """Updates status for multiple creators. Returns count of rows updated."""
    if not creator_ids:
        return 0
    placeholders = ",".join(["%s"] * len(creator_ids))
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        f"UPDATE creators SET status=%s, last_updated_at=%s WHERE id IN ({placeholders})",
        [status, now, *creator_ids],
    )
    conn.commit()
    return cur.rowcount


def start_run(conn, platform: str, seeds: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs (platform, seeds_used, started_at, status)
        VALUES (%s, %s, %s, 'running')
        RETURNING id
        """,
        (platform, json.dumps(seeds), datetime.now(timezone.utc).isoformat()),
    )
    row = cur.fetchone()
    conn.commit()
    return row["id"]


def finish_run(
    conn,
    run_id: int,
    status: str,
    stats: dict | None = None,
    error: str | None = None,
) -> None:
    stats = stats or {}
    conn.execute(
        """
        UPDATE pipeline_runs SET
            status              = %s,
            finished_at         = %s,
            creators_found      = %s,
            creators_qualified  = %s,
            apify_cost_usd      = %s,
            openai_cost_usd     = %s,
            error_message       = %s
        WHERE id = %s
        """,
        (
            status,
            datetime.now(timezone.utc).isoformat(),
            stats.get("creators_found"),
            stats.get("creators_qualified"),
            stats.get("apify_cost_usd"),
            stats.get("openai_cost_usd"),
            error,
            run_id,
        ),
    )
    conn.commit()


def insert_score_history(
    conn,
    creator_id: int,
    run_id: int,
    score: float,
    followers: int,
    engagement: float,
) -> None:
    conn.execute(
        """
        INSERT INTO score_history (creator_id, run_id, epic_trip_score, followers, avg_engagement, scored_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (creator_id, run_id, score, followers, engagement, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_score_history(conn, creator_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM score_history WHERE creator_id=%s ORDER BY scored_at ASC",
        (creator_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Search configs
# ---------------------------------------------------------------------------

def get_search_configs(
    conn,
    platform: str | None = None,
    active_only: bool = True,
    tag: str | None = None,
) -> list[dict]:
    conditions = []
    params: list = []
    if platform:
        conditions.append("platform = %s")
        params.append(platform)
    if active_only:
        conditions.append("active = TRUE")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(f"SELECT * FROM search_configs {where} ORDER BY platform, search_type, value", params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
        result.append(d)
    if tag:
        result = [r for r in result if tag in r["tags"]]
    return result


def upsert_search_config(conn, platform: str, search_type: str, value: str, active: bool = True, source: str = "manual", tags: list[str] | None = None) -> int:
    cur = conn.execute(
        """
        INSERT INTO search_configs (platform, search_type, value, active, source, tags)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT(platform, search_type, value) DO UPDATE SET
            active = EXCLUDED.active,
            source = EXCLUDED.source
        RETURNING id
        """,
        (platform, search_type, value, active, source, json.dumps(tags or [])),
    )
    row = cur.fetchone()
    conn.commit()
    return row["id"]


def update_search_config_tags(conn, config_id: int, tags: list[str]) -> None:
    conn.execute("UPDATE search_configs SET tags=%s WHERE id=%s", (json.dumps(tags), config_id))
    conn.commit()


def toggle_search_config(conn, config_id: int, active: bool) -> None:
    conn.execute("UPDATE search_configs SET active=%s WHERE id=%s", (active, config_id))
    conn.commit()


def delete_search_config(conn, config_id: int) -> None:
    conn.execute("DELETE FROM search_configs WHERE id=%s", (config_id,))
    conn.commit()


def seed_default_search_configs(conn) -> None:
    """Populates search_configs from config/seeds.py if table is empty."""
    row = conn.execute("SELECT COUNT(*) AS cnt FROM search_configs").fetchone()
    if row["cnt"] > 0:
        return
    from config.seeds import SEEDS
    for platform, types in SEEDS.items():
        for search_type, values in types.items():
            for value in values:
                upsert_search_config(conn, platform, search_type, value)
    logger.info("Seeded default search configs from config/seeds.py")


def get_unscored_creators(
    conn, platform: str | None = None
) -> list[Creator]:
    conditions = ["epic_trip_score IS NULL"]
    params: list = []
    if platform is not None:
        conditions.append("platform = %s")
        params.append(platform)
    where = "WHERE " + " AND ".join(conditions)
    rows = conn.execute(f"SELECT * FROM creators {where}", params).fetchall()
    return [_row_to_creator(r) for r in rows]
