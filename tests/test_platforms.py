from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(filename: str) -> dict:
    with open(os.path.join(FIXTURES_DIR, filename)) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Instagram tests
# ---------------------------------------------------------------------------

from platforms.instagram import (
    calculate_engagement as ig_engagement,
    classify_post_type,
    normalize_post as ig_normalize_post,
    normalize_profile as ig_normalize_profile,
)


def test_normalize_instagram_profile():
    raw = _load("instagram_profile_sample.json")
    creator = ig_normalize_profile(raw)
    assert creator.platform == "instagram"
    assert creator.username == "mochilero_andres"
    assert creator.display_name == "Andrés Viajero"
    assert creator.followers == 4200
    assert creator.following == 890
    assert creator.total_posts == 237
    assert creator.verified is False
    assert creator.business_account is False
    assert "Medellín" in (creator.location or "")


def test_normalize_instagram_video_post():
    raw = _load("instagram_video_post_sample.json")
    post = ig_normalize_post(raw, creator_id=1)
    assert post.platform == "instagram"
    assert post.post_type == "video"
    assert post.likes == 520
    assert post.comments == 43
    assert post.views == 14800
    assert post.engagement_rate == pytest.approx((520 + 43) / 14800)
    assert post.creator_id == 1
    hashtags = json.loads(post.hashtags)
    assert "mochilero" in hashtags


def test_normalize_instagram_image_post():
    raw = _load("instagram_image_post_sample.json")
    post = ig_normalize_post(raw, creator_id=2)
    assert post.post_type == "image"
    assert post.views == 0
    assert post.likes == 310
    assert post.comments == 28
    # image engagement uses followers
    assert post.engagement_rate == pytest.approx((310 + 28) / 4200)


def test_normalize_instagram_sidecar_post():
    raw = _load("instagram_sidecar_post_sample.json")
    post = ig_normalize_post(raw, creator_id=3)
    assert post.post_type == "sidecar"
    assert post.likes == 430
    assert post.engagement_rate == pytest.approx((430 + 67) / 4200)


def test_normalize_tiktok_profile():
    from platforms.tiktok import normalize_profile as tt_normalize_profile
    raw_videos = [_load("tiktok_video_sample.json")]
    creator = tt_normalize_profile(raw_videos)
    assert creator.platform == "tiktok"
    assert creator.username == "viajera_sofia"
    assert creator.display_name == "Sofía en el Mundo"
    assert creator.followers == 18500
    assert creator.verified is False


def test_normalize_tiktok_post():
    from platforms.tiktok import normalize_post as tt_normalize_post
    raw = _load("tiktok_video_sample.json")
    post = tt_normalize_post(raw, creator_id=5)
    assert post.platform == "tiktok"
    assert post.post_type == "video"
    assert post.likes == 3200
    assert post.comments == 215
    assert post.shares == 410
    assert post.views == 87000
    assert post.creator_id == 5
    hashtags = json.loads(post.hashtags)
    assert "mochilero" in hashtags


def test_classify_post_type_video():
    raw = {"type": "Video", "videoViewCount": 5000}
    assert classify_post_type(raw) == "video"


def test_classify_post_type_image():
    raw = {"type": "Image", "videoViewCount": 0}
    assert classify_post_type(raw) == "image"


def test_classify_post_type_sidecar():
    raw = {"type": "Sidecar", "childPosts": [{}]}
    assert classify_post_type(raw) == "sidecar"


# ---------------------------------------------------------------------------
# Engagement calculation tests
# ---------------------------------------------------------------------------

def test_engagement_video_uses_views():
    result = ig_engagement("video", likes=100, comments=10, views=2000, followers=5000)
    assert result == pytest.approx(110 / 2000)


def test_engagement_image_uses_followers():
    result = ig_engagement("image", likes=100, comments=10, views=0, followers=5000)
    assert result == pytest.approx(110 / 5000)


def test_engagement_tiktok_uses_plays():
    from platforms.tiktok import calculate_engagement as tt_engagement
    result = tt_engagement(likes=3200, comments=215, shares=410, plays=87000)
    assert result == pytest.approx((3200 + 215 + 410) / 87000)


def test_engagement_tiktok_zero_plays_returns_zero():
    from platforms.tiktok import calculate_engagement as tt_engagement
    result = tt_engagement(likes=100, comments=10, shares=5, plays=0)
    assert result == 0.0
