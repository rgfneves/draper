from __future__ import annotations

import logging

from config.filters import PARTIAL_KEYWORDS as _DEFAULT_PARTIAL_KEYWORDS
from config.filters import TRAVEL_KEYWORDS as _DEFAULT_TRAVEL_KEYWORDS

logger = logging.getLogger(__name__)

WEIGHTS: dict[str, float] = {
    "engagement": 0.30,
    "niche": 0.25,
    "followers": 0.20,
    "growth": 0.15,
    "activity": 0.10,
}


def score_engagement(avg_engagement: float) -> float:
    """Normalize 0-15% engagement to 0-1."""
    return min(avg_engagement / 0.15, 1.0)


def score_followers(count: int, min_f: int = 800, max_f: int = 50000) -> float:
    """
    Bell curve centred on sweet spot (2k-10k).
    Below min_f: 0.0
    800-2000: linear 0.4 to 0.8
    2000-10000: 0.8 to 1.0
    10000-50000: decay to 0.4
    Above 50000: 0.2
    """
    count = count or 0
    if count < min_f:
        return 0.0
    if count < 2000:
        # linear from 0.4 at 800 to 0.8 at 2000
        t = (count - 800) / (2000 - 800)
        return 0.4 + t * 0.4
    if count <= 10000:
        # linear from 0.8 at 2000 to 1.0 at 10000
        t = (count - 2000) / (10000 - 2000)
        return 0.8 + t * 0.2
    if count <= max_f:
        # decay from 1.0 at 10000 to 0.4 at 50000
        t = (count - 10000) / (max_f - 10000)
        return 1.0 - t * 0.6
    return 0.2


def score_niche(
    niche_label: str,
    ai_pass: bool | None = None,
    travel_keywords: list[str] | None = None,
    partial_keywords: list[str] | None = None,
) -> float:
    """
    1.0 if travel keywords present, 0.5 if partial match.
    Returns 0.0 if ai_pass is explicitly False.

    travel_keywords / partial_keywords: override defaults from config.filters
    to enable per-experiment keyword sets.
    """
    if ai_pass is False:
        return 0.0
    if not niche_label:
        return 0.0  # classificação falhou ou não rodou ainda — sem crédito
    kw_travel = travel_keywords if travel_keywords is not None else _DEFAULT_TRAVEL_KEYWORDS
    kw_partial = partial_keywords if partial_keywords is not None else _DEFAULT_PARTIAL_KEYWORDS
    niche_lower = niche_label.lower()
    for kw in kw_travel:
        if kw in niche_lower:
            return 1.0
    for kw in kw_partial:
        if kw in niche_lower:
            return 0.5
    return 0.3


def score_growth(history: list[dict]) -> float:
    """
    Compares followers now vs 30 days ago from score_history.
    Returns 0.5 (neutral) if no history.
    Maps -10% to +10% growth to 0-1 scale.
    """
    if not history or len(history) < 2:
        return 0.5

    # Sort by scored_at to get chronological order
    sorted_history = sorted(history, key=lambda h: h.get("scored_at") or "")

    latest = sorted_history[-1]
    # Find the entry closest to 30 days before latest
    latest_followers = latest.get("followers") or 0
    if latest_followers == 0:
        return 0.5

    # Use oldest available entry as baseline if we don't have exactly 30-day data
    baseline = sorted_history[0]
    baseline_followers = baseline.get("followers") or 0
    if baseline_followers == 0:
        return 0.5

    growth_rate = (latest_followers - baseline_followers) / baseline_followers
    # Map [-0.10, +0.10] to [0.0, 1.0]
    normalized = (growth_rate + 0.10) / 0.20
    return max(0.0, min(normalized, 1.0))


def score_activity(posts_last_30_days: int) -> float:
    """Linear: 0 posts = 0.0, 15+ posts = 1.0."""
    return min((posts_last_30_days or 0) / 15.0, 1.0)


def compute_epic_trip_score(
    creator_metrics: dict,
    travel_keywords: list[str] | None = None,
    partial_keywords: list[str] | None = None,
) -> dict:
    """
    Returns dict with individual scores and total EpicTripScore.

    Expected keys in creator_metrics:
    - avg_engagement: float
    - niche: str
    - ai_filter_pass: bool | None
    - followers: int
    - score_history: list[dict]  (optional, for growth)
    - posts_last_30_days: int

    travel_keywords / partial_keywords: override defaults for per-experiment scoring.
    """
    s_engagement = score_engagement(creator_metrics.get("avg_engagement") or 0.0)
    s_niche = score_niche(
        creator_metrics.get("niche") or "",
        creator_metrics.get("ai_filter_pass"),
        travel_keywords=travel_keywords,
        partial_keywords=partial_keywords,
    )
    s_followers = score_followers(creator_metrics.get("followers") or 0)
    s_growth = score_growth(creator_metrics.get("score_history") or [])
    s_activity = score_activity(creator_metrics.get("posts_last_30_days") or 0)

    epic = (
        WEIGHTS["engagement"] * s_engagement
        + WEIGHTS["niche"] * s_niche
        + WEIGHTS["followers"] * s_followers
        + WEIGHTS["growth"] * s_growth
        + WEIGHTS["activity"] * s_activity
    )

    return {
        "score_engagement": round(s_engagement, 6),
        "score_niche": round(s_niche, 6),
        "score_followers": round(s_followers, 6),
        "score_growth": round(s_growth, 6),
        "score_activity": round(s_activity, 6),
        "epic_trip_score": round(epic, 6),
    }
