from __future__ import annotations

import pytest

from db.models import Creator
from pipeline.initial_filter import passes_initial_filter


def test_initial_filter_keyword_no_false_positive():
    """'business' in excluded_keywords must NOT match 'businesswoman' in bio."""
    c = Creator(
        platform="instagram",
        username="test_fp",
        followers=5000,
        bio="I am a businesswoman who loves travel",
        is_private=False,
    )
    result = passes_initial_filter(
        c, "instagram",
        excluded_keywords=["business"],
        min_followers=1000,
        max_followers=100000,
    )
    assert result is True, "word 'business' should not match 'businesswoman'"


def test_initial_filter_keyword_exact_match_excluded():
    """'business' in excluded_keywords MUST match exact word 'business' in bio."""
    c = Creator(
        platform="instagram",
        username="test_exact",
        followers=5000,
        bio="I run a business account for my brand",
        is_private=False,
    )
    result = passes_initial_filter(
        c, "instagram",
        excluded_keywords=["business"],
        min_followers=1000,
        max_followers=100000,
    )
    assert result is False, "word 'business' must match exact word in bio"
