from __future__ import annotations

import pytest

from pipeline.scoring import (
    WEIGHTS,
    compute_epic_trip_score,
    score_activity,
    score_engagement,
    score_followers,
    score_growth,
    score_niche,
)


# ---------------------------------------------------------------------------
# score_engagement
# ---------------------------------------------------------------------------

def test_score_engagement_zero():
    assert score_engagement(0.0) == 0.0


def test_score_engagement_max_clamps_to_1():
    assert score_engagement(0.20) == pytest.approx(1.0)
    assert score_engagement(0.50) == pytest.approx(1.0)


def test_score_engagement_mid_range():
    # 7.5% → 0.5
    result = score_engagement(0.075)
    assert result == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# score_followers
# ---------------------------------------------------------------------------

def test_score_followers_below_min_returns_zero():
    assert score_followers(0) == 0.0
    assert score_followers(799) == 0.0


def test_score_followers_sweet_spot_5000():
    result = score_followers(5000)
    # 5000 is in 2000-10000 range → between 0.8 and 1.0
    assert 0.8 <= result <= 1.0


def test_score_followers_above_max():
    result = score_followers(60000)
    assert result == pytest.approx(0.2)


def test_score_followers_boundary_800():
    result = score_followers(800)
    assert result == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# score_niche
# ---------------------------------------------------------------------------

def test_score_niche_travel_keywords():
    assert score_niche("mochilero travel") == pytest.approx(1.0)
    assert score_niche("budget travel blogger") == pytest.approx(1.0)
    assert score_niche("viajero independiente") == pytest.approx(1.0)


def test_score_niche_partial_niche():
    assert score_niche("lifestyle vlog") == pytest.approx(0.5)
    assert score_niche("content creator") == pytest.approx(0.5)


def test_score_niche_ai_fail_overrides_to_zero():
    assert score_niche("mochilero travel", ai_pass=False) == pytest.approx(0.0)
    assert score_niche("viajes budget", ai_pass=False) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# score_growth
# ---------------------------------------------------------------------------

def test_score_growth_no_history_returns_neutral():
    assert score_growth([]) == pytest.approx(0.5)
    assert score_growth([{"followers": 3000, "scored_at": "2024-01-01"}]) == pytest.approx(0.5)


def test_score_growth_positive():
    history = [
        {"followers": 3000, "scored_at": "2024-01-01"},
        {"followers": 3300, "scored_at": "2024-02-01"},  # +10%
    ]
    result = score_growth(history)
    assert result == pytest.approx(1.0)


def test_score_growth_negative():
    history = [
        {"followers": 3000, "scored_at": "2024-01-01"},
        {"followers": 2700, "scored_at": "2024-02-01"},  # -10%
    ]
    result = score_growth(history)
    assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# score_activity
# ---------------------------------------------------------------------------

def test_score_activity_zero_posts():
    assert score_activity(0) == pytest.approx(0.0)


def test_score_activity_max_posts():
    assert score_activity(15) == pytest.approx(1.0)
    assert score_activity(30) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# compute_epic_trip_score
# ---------------------------------------------------------------------------

def test_epic_trip_score_weights_sum_to_one():
    total = sum(WEIGHTS.values())
    assert total == pytest.approx(1.0)


def test_epic_trip_score_perfect_profile():
    metrics = {
        "avg_engagement": 0.15,
        "niche": "mochilero travel",
        "ai_filter_pass": True,
        "followers": 5000,
        "score_history": [
            {"followers": 4545, "scored_at": "2024-01-01"},
            {"followers": 5000, "scored_at": "2024-02-01"},
        ],
        "posts_last_30_days": 15,
    }
    result = compute_epic_trip_score(metrics)
    assert result["epic_trip_score"] > 0.8
    assert result["score_engagement"] == pytest.approx(1.0)
    assert result["score_niche"] == pytest.approx(1.0)
    assert result["score_activity"] == pytest.approx(1.0)


def test_epic_trip_score_worst_profile():
    metrics = {
        "avg_engagement": 0.0,
        "niche": "luxury travel",
        "ai_filter_pass": False,
        "followers": 0,
        "score_history": [],
        "posts_last_30_days": 0,
    }
    result = compute_epic_trip_score(metrics)
    # With ai_pass=False, niche score=0; engagement=0; followers=0; activity=0; growth=0.5
    assert result["epic_trip_score"] < 0.2
    assert result["score_niche"] == pytest.approx(0.0)


def test_compute_returns_all_components():
    metrics = {
        "avg_engagement": 0.05,
        "niche": "travel",
        "followers": 3000,
        "posts_last_30_days": 8,
    }
    result = compute_epic_trip_score(metrics)
    expected_keys = {
        "score_engagement", "score_niche", "score_followers",
        "score_growth", "score_activity", "epic_trip_score",
    }
    assert expected_keys == set(result.keys())
    for v in result.values():
        assert isinstance(v, float)
