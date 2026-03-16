from __future__ import annotations


def render_filters() -> dict:
    """
    Renders Streamlit sidebar filter controls.
    Returns dict of active filter values.
    """
    import streamlit as st

    st.sidebar.header("Filters")

    platforms = st.sidebar.multiselect(
        "Platform",
        options=["Instagram", "TikTok"],
        default=["Instagram", "TikTok"],
    )

    followers_min, followers_max = st.sidebar.slider(
        "Followers range",
        min_value=0,
        max_value=100_000,
        value=(0, 100_000),
        step=500,
    )

    engagement_min, engagement_max = st.sidebar.slider(
        "Engagement range",
        min_value=0.0,
        max_value=0.20,
        value=(0.0, 0.20),
        step=0.005,
        format="%.3f",
    )

    epic_score_min = st.sidebar.slider(
        "Min EpicTripScore",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.05,
        format="%.2f",
    )

    ai_filter_only = st.sidebar.checkbox("AI Filter passed only", value=False)

    return {
        "platforms": [p.lower() for p in platforms],
        "followers_min": followers_min,
        "followers_max": followers_max,
        "engagement_min": engagement_min,
        "engagement_max": engagement_max,
        "epic_score_min": epic_score_min,
        "ai_filter_only": ai_filter_only,
    }
