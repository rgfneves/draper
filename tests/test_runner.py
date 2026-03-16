from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from db.models import Creator, Post
from db.repository import get_all_creators, get_score_history, start_run


def _mock_discover(usernames):
    return usernames


def _make_creator_list():
    return [
        Creator(
            platform="instagram",
            username="test_user_1",
            followers=3500,
            bio="Mochilero viajando el mundo",
            avg_engagement=0.06,
            posts_last_30_days=6,
            is_active=True,
            status="discovered",
        )
    ]


def _make_post_list(creator_id=0):
    return [
        Post(
            creator_id=creator_id,
            platform="instagram",
            post_id="post_001",
            post_type="image",
            published_at="2025-03-01T10:00:00",
            engagement_rate=0.06,
        )
    ]


@patch("pipeline.runner.get_connection")
@patch("pipeline.discovery.discover")
def test_dry_run_prints_info_no_api_calls(mock_discover, mock_conn, pg_conn, capsys):
    mock_conn.return_value = pg_conn
    mock_discover.return_value = []

    # Dry run should not call any Apify functions
    with patch("platforms.apify_client.run_actor") as mock_run_actor:
        from pipeline.runner import main
        main(["--platform", "instagram", "--limit", "50", "--dry-run"])
        mock_run_actor.assert_not_called()


@patch("pipeline.runner.get_connection")
@patch("pipeline.scraping.fetch_profiles_and_posts")
@patch("pipeline.discovery.discover")
def test_skip_scrape_reads_from_db(mock_discover, mock_fetch, mock_conn, pg_conn):
    mock_conn.return_value = pg_conn

    # Pre-populate DB
    from db.repository import upsert_creator
    c = Creator(
        platform="instagram",
        username="existing_user",
        followers=2000,
        bio="backpacker",
        avg_engagement=0.05,
        posts_last_30_days=5,
        is_active=True,
    )
    upsert_creator(pg_conn, c)

    with patch("pipeline.niche_classifier.classify_niche", return_value="travel"):
        with patch("pipeline.ai_filter.evaluate_batch", return_value=[]):
            from pipeline.runner import main
            main(["--platform", "instagram", "--skip-scrape", "--skip-ai-filter"])

    mock_fetch.assert_not_called()
    mock_discover.assert_not_called()


@patch("pipeline.runner.get_connection")
@patch("pipeline.scraping.fetch_profiles_and_posts")
@patch("pipeline.discovery.discover")
def test_full_run_saves_creators_to_db(mock_discover, mock_fetch, mock_conn, pg_conn):
    mock_conn.return_value = pg_conn
    mock_discover.return_value = ["test_creator"]
    mock_fetch.return_value = (_make_creator_list(), _make_post_list())

    with patch("pipeline.niche_classifier.classify_niche", return_value="mochilero travel"):
        with patch("pipeline.ai_filter.evaluate_batch", return_value=[]):
            from pipeline.runner import main
            main(["--platform", "instagram", "--limit", "10", "--skip-ai-filter"])

    creators = get_all_creators(pg_conn, platform="instagram")
    assert len(creators) >= 1
    assert any(c.username == "test_user_1" for c in creators)


@patch("pipeline.runner.get_connection")
@patch("pipeline.scraping.fetch_profiles_and_posts")
@patch("pipeline.discovery.discover")
def test_run_tracks_pipeline_run_record(mock_discover, mock_fetch, mock_conn, pg_conn):
    mock_conn.return_value = pg_conn
    mock_discover.return_value = ["track_user"]
    mock_fetch.return_value = (_make_creator_list(), [])

    with patch("pipeline.niche_classifier.classify_niche", return_value="travel"):
        with patch("pipeline.ai_filter.evaluate_batch", return_value=[]):
            from pipeline.runner import main
            main(["--platform", "instagram", "--limit", "10", "--skip-ai-filter"])

    row = pg_conn.execute(
        "SELECT * FROM pipeline_runs WHERE platform='instagram'"
    ).fetchone()
    assert row is not None
    assert row["status"] == "completed"
    assert row["finished_at"] is not None


@patch("pipeline.runner.get_connection")
@patch("pipeline.discovery.discover")
def test_run_handles_discovery_failure_gracefully(mock_discover, mock_conn, pg_conn):
    mock_conn.return_value = pg_conn
    mock_discover.side_effect = RuntimeError("Apify failure")

    from pipeline.runner import main
    with pytest.raises(SystemExit):
        main(["--platform", "instagram", "--limit", "10"])

    row = pg_conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["status"] == "failed"
    assert "Apify failure" in (row["error_message"] or "")


@patch("pipeline.runner.get_connection")
@patch("pipeline.scraping.fetch_profiles_and_posts")
@patch("pipeline.discovery.discover")
def test_run_creates_score_history_entry(mock_discover, mock_fetch, mock_conn, pg_conn):
    mock_conn.return_value = pg_conn
    mock_discover.return_value = ["history_user"]
    mock_fetch.return_value = (_make_creator_list(), [])

    with patch("pipeline.niche_classifier.classify_niche", return_value="travel"):
        with patch("pipeline.ai_filter.evaluate_batch", return_value=[]):
            from pipeline.runner import main
            main(["--platform", "instagram", "--skip-ai-filter"])

    creators = get_all_creators(pg_conn, platform="instagram")
    assert creators
    cid = creators[0].id
    history = get_score_history(pg_conn, cid)
    assert len(history) >= 1
    assert history[0]["epic_trip_score"] is not None
