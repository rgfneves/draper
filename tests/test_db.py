from __future__ import annotations

import pytest

from db.models import Creator, Post
from db.repository import (
    finish_run,
    get_all_creators,
    get_creator_by_username,
    get_score_history,
    get_unscored_creators,
    insert_score_history,
    start_run,
    update_creator_score,
    upsert_creator,
    upsert_post,
)


def _make_creator(**kwargs) -> Creator:
    defaults = dict(
        platform="instagram",
        username="traveler_juan",
        display_name="Juan Viajero",
        bio="Backpacker life",
        followers=3000,
        following=500,
        total_posts=120,
        verified=False,
        business_account=False,
    )
    defaults.update(kwargs)
    return Creator(**defaults)


def test_create_schema_has_all_tables(pg_conn):
    rows = pg_conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    ).fetchall()
    tables = {r["table_name"] for r in rows}
    assert "creators" in tables
    assert "posts" in tables
    assert "pipeline_runs" in tables
    assert "score_history" in tables
    assert "outreach" in tables


def test_upsert_creator_new(pg_conn):
    creator = _make_creator()
    cid = upsert_creator(pg_conn, creator)
    assert isinstance(cid, int)
    assert cid > 0


def test_upsert_creator_existing_updates(pg_conn):
    creator = _make_creator()
    cid1 = upsert_creator(pg_conn, creator)
    creator.followers = 9999
    cid2 = upsert_creator(pg_conn, creator)
    assert cid1 == cid2
    fetched = get_creator_by_username(pg_conn, "instagram", "traveler_juan")
    assert fetched.followers == 9999


def test_upsert_creator_unique_constraint(pg_conn):
    c1 = _make_creator(platform="instagram", username="same_user", followers=1000)
    c2 = _make_creator(platform="instagram", username="same_user", followers=2000)
    id1 = upsert_creator(pg_conn, c1)
    id2 = upsert_creator(pg_conn, c2)
    assert id1 == id2
    rows = pg_conn.execute("SELECT count(*) AS cnt FROM creators WHERE username='same_user'").fetchone()
    assert rows["cnt"] == 1


def test_upsert_post_deduplication(pg_conn):
    creator = _make_creator()
    cid = upsert_creator(pg_conn, creator)
    post = Post(creator_id=cid, platform="instagram", post_id="abc123", post_type="image", likes=100, comments=10)
    pid1 = upsert_post(pg_conn, post)
    post.likes = 200
    pid2 = upsert_post(pg_conn, post)
    assert pid1 == pid2
    rows = pg_conn.execute("SELECT count(*) AS cnt FROM posts WHERE post_id='abc123'").fetchone()
    assert rows["cnt"] == 1
    updated = pg_conn.execute("SELECT likes FROM posts WHERE post_id='abc123'").fetchone()
    assert updated["likes"] == 200


def test_get_all_creators_filter_by_platform(pg_conn):
    upsert_creator(pg_conn, _make_creator(platform="instagram", username="ig_user"))
    upsert_creator(pg_conn, _make_creator(platform="tiktok", username="tt_user"))
    ig = get_all_creators(pg_conn, platform="instagram")
    tt = get_all_creators(pg_conn, platform="tiktok")
    assert all(c.platform == "instagram" for c in ig)
    assert all(c.platform == "tiktok" for c in tt)
    assert len(ig) == 1
    assert len(tt) == 1


def test_get_all_creators_filter_by_status(pg_conn):
    upsert_creator(pg_conn, _make_creator(username="user_a", status="discovered"))
    upsert_creator(pg_conn, _make_creator(username="user_b", status="qualified"))
    discovered = get_all_creators(pg_conn, status="discovered")
    qualified = get_all_creators(pg_conn, status="qualified")
    assert len(discovered) == 1
    assert len(qualified) == 1
    assert discovered[0].username == "user_a"
    assert qualified[0].username == "user_b"


def test_start_and_finish_run(pg_conn):
    run_id = start_run(pg_conn, "instagram", {"hashtags": ["mochilero"]})
    assert isinstance(run_id, int)
    row = pg_conn.execute("SELECT * FROM pipeline_runs WHERE id=%s", (run_id,)).fetchone()
    assert row["status"] == "running"
    finish_run(pg_conn, run_id, "completed", stats={"creators_found": 10, "creators_qualified": 5})
    row = pg_conn.execute("SELECT * FROM pipeline_runs WHERE id=%s", (run_id,)).fetchone()
    assert row["status"] == "completed"
    assert row["creators_found"] == 10
    assert row["creators_qualified"] == 5
    assert row["finished_at"] is not None


def test_score_history_tracking(pg_conn):
    cid = upsert_creator(pg_conn, _make_creator())
    run_id = start_run(pg_conn, "instagram", {})
    insert_score_history(pg_conn, cid, run_id, 0.75, 3000, 0.08)
    history = get_score_history(pg_conn, cid)
    assert len(history) == 1
    assert history[0]["epic_trip_score"] == 0.75
    assert history[0]["followers"] == 3000


def test_get_creator_by_username_not_found(pg_conn):
    result = get_creator_by_username(pg_conn, "instagram", "nonexistent_user")
    assert result is None


def test_update_creator_score(pg_conn):
    cid = upsert_creator(pg_conn, _make_creator())
    scores = {
        "epic_trip_score": 0.82,
        "score_engagement": 0.9,
        "score_niche": 1.0,
        "score_followers": 0.8,
        "score_growth": 0.5,
        "score_activity": 0.7,
    }
    update_creator_score(pg_conn, cid, scores)
    fetched = get_creator_by_username(pg_conn, "instagram", "traveler_juan")
    assert fetched.epic_trip_score == pytest.approx(0.82)
    assert fetched.score_engagement == pytest.approx(0.9)


def test_get_unscored_creators(pg_conn):
    cid1 = upsert_creator(pg_conn, _make_creator(username="unscored_user"))
    cid2 = upsert_creator(pg_conn, _make_creator(username="scored_user"))
    update_creator_score(pg_conn, cid2, {"epic_trip_score": 0.5})
    unscored = get_unscored_creators(pg_conn)
    assert len(unscored) == 1
    assert unscored[0].username == "unscored_user"


def test_upsert_creator_preserves_niche_on_empty_string(pg_conn):
    """Empty-string niche must not overwrite an existing classified niche."""
    c = _make_creator(username="nichetest", niche="budget travel")
    cid = upsert_creator(pg_conn, c)

    # Simulate a second upsert where niche comes back as "" (GPT failure)
    c2 = _make_creator(username="nichetest", niche="")
    upsert_creator(pg_conn, c2)

    row = pg_conn.execute(
        "SELECT niche FROM creators WHERE id=%s", (cid,)
    ).fetchone()
    assert row["niche"] == "budget travel", "niche must be preserved when update sends empty string"
