from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from config.filters import EXCLUDED_KEYWORDS
from db.models import Creator, Post
from pipeline.analysis import analyze_creator, is_irrelevant_by_keywords


def _make_post(days_ago: float, engagement: float = 0.05) -> Post:
    published_at = (datetime.now(tz=timezone.utc) - timedelta(days=days_ago)).isoformat()
    return Post(
        platform="instagram",
        post_id=f"post_{days_ago}",
        post_type="image",
        published_at=published_at,
        engagement_rate=engagement,
    )


def _make_creator(platform: str = "instagram") -> Creator:
    return Creator(platform=platform, username="test_user", followers=3000)


def test_analyze_creator_active_profile():
    creator = _make_creator()
    posts = [_make_post(d) for d in [2, 7, 14, 20, 25]]
    result = analyze_creator(creator, posts)
    assert result["posts_last_30_days"] == 5
    assert result["is_active"] is True
    assert result["avg_engagement"] == pytest.approx(0.05)


def test_analyze_creator_inactive_low_posts():
    creator = _make_creator()
    # Only 2 posts in last 30 days — below min_posts_30_days=4
    posts = [_make_post(10), _make_post(20)]
    result = analyze_creator(creator, posts)
    assert result["posts_last_30_days"] == 2
    assert result["is_active"] is False


def test_analyze_creator_no_posts():
    creator = _make_creator()
    result = analyze_creator(creator, [])
    assert result["posts_last_30_days"] == 0
    assert result["avg_engagement"] == 0.0
    assert result["is_active"] is False
    assert result["posting_frequency"] == 0.0


def test_posting_frequency_calculation():
    creator = _make_creator()
    # 9 posts within 90 days → 9/90 = 0.1 posts/day
    posts = [_make_post(d) for d in [5, 15, 25, 35, 45, 55, 65, 75, 85]]
    result = analyze_creator(creator, posts)
    assert result["posts_last_90_days"] == 9
    assert result["posting_frequency"] == pytest.approx(9 / 90.0)


def test_aging_breakdown_correct_buckets():
    creator = _make_creator()
    posts = [
        _make_post(10),   # 0-30
        _make_post(25),   # 0-30
        _make_post(45),   # 31-60
        _make_post(70),   # 61-90
        _make_post(100),  # over_90
    ]
    result = analyze_creator(creator, posts)
    ab = result["aging_breakdown"]
    assert ab["0_30"] == 2
    assert ab["31_60"] == 1
    assert ab["61_90"] == 1
    assert ab["over_90"] == 1


def test_is_irrelevant_bio_luxury():
    assert is_irrelevant_by_keywords("I love luxury travel", [], EXCLUDED_KEYWORDS) is True


def test_is_irrelevant_caption_luxury():
    assert is_irrelevant_by_keywords("", ["Staying at 5-star hotels in Bali"], EXCLUDED_KEYWORDS) is True


def test_not_irrelevant_clean_profile():
    assert is_irrelevant_by_keywords(
        "Backpacker viajando el mundo con poco dinero",
        ["Semana en Roma con 200 euros #mochilero"],
        EXCLUDED_KEYWORDS,
    ) is False


def test_is_irrelevant_case_insensitive():
    assert is_irrelevant_by_keywords("I adore LUXURY experiences", [], EXCLUDED_KEYWORDS) is True
    assert is_irrelevant_by_keywords("", ["BUSINESS CLASS flights"], EXCLUDED_KEYWORDS) is True
