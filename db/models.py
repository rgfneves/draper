from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Creator:
    id: Optional[int] = None
    platform: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    link_in_bio: Optional[str] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    total_posts: Optional[int] = None
    verified: Optional[bool] = None
    business_account: Optional[bool] = None
    is_private: Optional[bool] = None
    profile_pic_url: Optional[str] = None
    email: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    niche: Optional[str] = None
    ai_filter_pass: Optional[bool] = None
    ai_filter_reason: Optional[str] = None
    epic_trip_score: Optional[float] = None
    score_engagement: Optional[float] = None
    score_niche: Optional[float] = None
    score_followers: Optional[float] = None
    score_growth: Optional[float] = None
    score_activity: Optional[float] = None
    avg_engagement: Optional[float] = None
    posts_last_30_days: Optional[int] = None
    posting_frequency: Optional[float] = None
    is_active: Optional[bool] = None
    discovered_via_type: Optional[str] = None
    discovered_via_value: Optional[str] = None
    status: str = "discovered"
    is_lead: bool = False
    first_seen_at: Optional[str] = None
    last_updated_at: Optional[str] = None


@dataclass
class Post:
    id: Optional[int] = None
    creator_id: Optional[int] = None
    platform: Optional[str] = None
    post_id: Optional[str] = None
    post_type: Optional[str] = None
    post_url: Optional[str] = None
    published_at: Optional[str] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    views: Optional[int] = None
    engagement_rate: Optional[float] = None
    caption: Optional[str] = None
    hashtags: Optional[str] = None  # JSON array string


@dataclass
class PipelineRun:
    id: Optional[int] = None
    platform: Optional[str] = None
    seeds_used: Optional[str] = None  # JSON string
    creators_found: Optional[int] = None
    creators_qualified: Optional[int] = None
    apify_cost_usd: Optional[float] = None
    openai_cost_usd: Optional[float] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str = "running"
    error_message: Optional[str] = None


@dataclass
class ScoreHistory:
    id: Optional[int] = None
    creator_id: Optional[int] = None
    run_id: Optional[int] = None
    epic_trip_score: Optional[float] = None
    followers: Optional[int] = None
    avg_engagement: Optional[float] = None
    scored_at: Optional[str] = None


@dataclass
class Outreach:
    id: Optional[int] = None
    creator_id: Optional[int] = None
    contacted_at: Optional[str] = None
    channel: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
