from __future__ import annotations


def render(conn) -> None:
    """
    Calibration page:
    Left: filter controls + free text prompt for ad-hoc AI re-evaluation
    Right: filtered results table sorted by epic_trip_score desc + Export CSV
    Shows count of matching profiles.
    """
    import pandas as pd
    import streamlit as st

    from dashboard.components.export import download_csv_button
    from dashboard.components.filters import render_filters

    st.title("Draper — Calibration")

    filters = render_filters()

    # Load all creators
    rows = conn.execute("SELECT * FROM creators").fetchall()
    if not rows:
        st.info("No creators in the database yet.")
        return

    df = pd.DataFrame([dict(r) for r in rows])

    # Apply filters
    if filters["platforms"]:
        df = df[df["platform"].isin(filters["platforms"])]

    if "followers" in df.columns:
        df = df[
            (df["followers"] >= filters["followers_min"])
            & (df["followers"] <= filters["followers_max"])
        ]

    if "avg_engagement" in df.columns:
        eng = df["avg_engagement"].fillna(0)
        df = df[
            (eng >= filters["engagement_min"])
            & (eng <= filters["engagement_max"])
        ]

    if "epic_trip_score" in df.columns:
        df = df[df["epic_trip_score"].fillna(0) >= filters["epic_score_min"]]

    if filters["ai_filter_only"] and "ai_filter_pass" in df.columns:
        df = df[df["ai_filter_pass"] == True]  # noqa: E712

    # Sort
    if "epic_trip_score" in df.columns:
        df = df.sort_values("epic_trip_score", ascending=False)

    left_col, right_col = st.columns([1, 2])

    with left_col:
        st.subheader("Ad-hoc AI Re-evaluation")
        prompt_text = st.text_area(
            "Custom evaluation prompt",
            placeholder="E.g. 'Focus on creators who mention South America and volunteer travel'",
            height=120,
        )
        if st.button("Run AI Re-evaluation") and prompt_text.strip():
            st.warning(
                "Ad-hoc re-evaluation would call GPT-4o-mini with your custom prompt. "
                "Connect to pipeline.ai_filter to implement."
            )

    with right_col:
        st.subheader(f"Matching Profiles ({len(df)})")
        display_cols = [
            c for c in [
                "username", "platform", "followers", "avg_engagement",
                "epic_trip_score", "niche", "ai_filter_pass", "status",
            ]
            if c in df.columns
        ]
        st.dataframe(df[display_cols], use_container_width=True)
        download_csv_button(df[display_cols], filename="draper_calibration.csv")
