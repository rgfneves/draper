from __future__ import annotations

"""
Full pipeline integration tests with mocked Apify + OpenAI.
All tests use ephemeral PostgreSQL via testing.postgresql.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from db.models import Creator, Post
from db.repository import (
    get_all_creators,
    get_score_history,
    upsert_creator,
    upsert_post,
)


def _ig_creator(username: str, followers: int = 3500) -> Creator:
    return Creator(
        platform="instagram",
        username=username,
        display_name=username.replace("_", " ").title(),
        bio="Mochilero viajando barato por el mundo",
        followers=followers,
        following=400,
        total_posts=150,
        verified=False,
        business_account=False,
        avg_engagement=0.07,
        posts_last_30_days=6,
        is_active=True,
        status="discovered",
    )


def _tt_creator(username: str, followers: int = 15000) -> Creator:
    return Creator(
        platform="tiktok",
        username=username,
        display_name=username.replace("_", " ").title(),
        bio="Viajero de TikTok #mochilero",
        followers=followers,
        following=200,
        verified=False,
        business_account=False,
        avg_engagement=0.05,
        posts_last_30_days=8,
        is_active=True,
        status="discovered",
    )


def _make_posts(creator_id: int, platform: str, n: int = 5) -> list[Post]:
    posts = []
    for i in range(n):
        days_ago = i * 5 + 2
        dt = (datetime.now(tz=timezone.utc) - timedelta(days=days_ago)).isoformat()
        posts.append(Post(
            creator_id=creator_id,
            platform=platform,
            post_id=f"{platform}_{creator_id}_{i}",
            post_type="video" if platform == "tiktok" else "image",
            published_at=dt,
            likes=300 + i * 50,
            comments=20 + i * 5,
            shares=10,
            views=8000 + i * 1000,
            engagement_rate=0.07,
            caption=f"Día {i+1} viajando barato #mochilero",
            hashtags=json.dumps(["mochilero", "viajes", "lowcost"]),
        ))
    return posts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_pipeline(conn, platform: str, creators: list[Creator], posts: list[Post]):
    """Simulate a full pipeline pass with pre-built creators/posts."""
    from db.repository import (
        finish_run,
        get_score_history,
        insert_score_history,
        start_run,
        update_creator_ai_filter,
        update_creator_score,
        update_creator_status,
    )
    from pipeline.analysis import analyze_creator, is_irrelevant_by_keywords
    from pipeline.scoring import compute_epic_trip_score
    from config.filters import EXCLUDED_KEYWORDS

    run_id = start_run(conn, platform, {})

    # Upsert creators and build id map
    creator_ids: dict[str, int] = {}
    for creator in creators:
        cid = upsert_creator(conn, creator)
        if creator.username:
            creator_ids[creator.username.lower()] = cid

    # Upsert posts — assign a valid creator_id (use first creator if unresolved)
    default_cid = list(creator_ids.values())[0] if creator_ids else None
    for post in posts:
        if post.creator_id == 0 and default_cid is not None:
            post.creator_id = default_cid
        if post.creator_id:
            upsert_post(conn, post)

    # Analyze + score
    db_creators = get_all_creators(conn, platform=platform)
    for creator in db_creators:
        if creator.id is None:
            continue
        post_rows = conn.execute(
            "SELECT * FROM posts WHERE creator_id=%s", (creator.id,)
        ).fetchall()
        creator_posts = [
            Post(
                creator_id=r["creator_id"],
                platform=r["platform"],
                post_id=r["post_id"],
                published_at=r["published_at"],
                engagement_rate=r["engagement_rate"],
            )
            for r in post_rows
        ]
        metrics = analyze_creator(creator, creator_posts)
        creator.avg_engagement = metrics["avg_engagement"]
        creator.posts_last_30_days = metrics["posts_last_30_days"]
        creator.posting_frequency = metrics["posting_frequency"]
        creator.is_active = metrics["is_active"]
        upsert_creator(conn, creator)

        # AI filter mock
        update_creator_ai_filter(conn, creator.id, True, "Authentic traveler")

        history = get_score_history(conn, creator.id)
        score_metrics = {
            "avg_engagement": creator.avg_engagement or 0.0,
            "niche": "mochilero travel",
            "ai_filter_pass": True,
            "followers": creator.followers or 0,
            "score_history": history,
            "posts_last_30_days": creator.posts_last_30_days or 0,
        }
        scores = compute_epic_trip_score(score_metrics)
        update_creator_score(conn, creator.id, scores)
        insert_score_history(conn, creator.id, run_id, scores["epic_trip_score"], creator.followers or 0, creator.avg_engagement or 0.0)

    finish_run(conn, run_id, "completed", stats={"creators_found": len(creators), "creators_qualified": len(creators)})
    return run_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_full_pipeline_instagram_e2e(pg_conn):
    creators = [_ig_creator(f"ig_user_{i}") for i in range(3)]
    all_posts = []
    for i, c in enumerate(creators):
        cid_temp = i + 1
        for p in _make_posts(cid_temp, "instagram"):
            p.creator_id = 0  # will be resolved after upsert
            all_posts.append(p)

    run_id = _run_pipeline(pg_conn, "instagram", creators, all_posts)

    db_creators = get_all_creators(pg_conn, platform="instagram")
    assert len(db_creators) == 3
    for c in db_creators:
        assert c.epic_trip_score is not None
        assert 0.0 <= c.epic_trip_score <= 1.0


def test_full_pipeline_tiktok_e2e(pg_conn):
    creators = [_tt_creator(f"tt_user_{i}", followers=10000 + i * 2000) for i in range(2)]
    run_id = _run_pipeline(pg_conn, "tiktok", creators, [])

    db_creators = get_all_creators(pg_conn, platform="tiktok")
    assert len(db_creators) == 2
    for c in db_creators:
        assert c.epic_trip_score is not None


def test_pipeline_result_visible_in_db(pg_conn):
    creators = [_ig_creator("visible_user", followers=5000)]
    _run_pipeline(pg_conn, "instagram", creators, [])

    result = pg_conn.execute(
        "SELECT * FROM creators WHERE username='visible_user'"
    ).fetchone()
    assert result is not None
    assert result["epic_trip_score"] is not None
    assert result["ai_filter_pass"] is True


def test_rescore_without_rescrape(pg_conn):
    creators = [_ig_creator("rescore_user", followers=4000)]
    _run_pipeline(pg_conn, "instagram", creators, [])

    # Modify followers in DB and run again
    pg_conn.execute(
        "UPDATE creators SET followers=6000 WHERE username='rescore_user'"
    )
    pg_conn.commit()

    _run_pipeline(pg_conn, "instagram", creators, [])

    history = pg_conn.execute(
        "SELECT * FROM score_history sh JOIN creators c ON sh.creator_id=c.id WHERE c.username='rescore_user' ORDER BY sh.scored_at"
    ).fetchall()
    assert len(history) >= 2


def test_deduplication_same_username_different_runs(pg_conn):
    creator = _ig_creator("dedup_user", followers=2500)

    _run_pipeline(pg_conn, "instagram", [creator], [])
    _run_pipeline(pg_conn, "instagram", [creator], [])

    count = pg_conn.execute(
        "SELECT count(*) AS cnt FROM creators WHERE username='dedup_user'"
    ).fetchone()["cnt"]
    assert count == 1


def test_score_history_accumulates_across_runs(pg_conn):
    creator = _ig_creator("history_user", followers=3000)

    _run_pipeline(pg_conn, "instagram", [creator], [])
    # Change followers between runs
    pg_conn.execute("UPDATE creators SET followers=3300 WHERE username='history_user'")
    pg_conn.commit()
    creator.followers = 3300
    _run_pipeline(pg_conn, "instagram", [creator], [])

    creator_row = pg_conn.execute(
        "SELECT id FROM creators WHERE username='history_user'"
    ).fetchone()
    history = get_score_history(pg_conn, creator_row["id"])
    assert len(history) >= 2
    # Latest entry should reflect updated followers
    assert any(h["followers"] == 3300 for h in history)
