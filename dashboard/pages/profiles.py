from __future__ import annotations


def render(conn) -> None:
    """
    Profiles page:
    - Search by username
    - Clickable profile links
    - Expandable detail view showing score breakdown + recent posts
    """
    import json

    import pandas as pd
    import streamlit as st

    st.title("Draper — Profiles")

    search_query = st.text_input("Search by username", placeholder="e.g. mochilero_andres")

    rows = conn.execute("SELECT * FROM creators ORDER BY epic_trip_score DESC").fetchall()
    if not rows:
        st.info("No creators in the database yet.")
        return

    df = pd.DataFrame([dict(r) for r in rows])

    if search_query.strip():
        df = df[df["username"].str.contains(search_query.strip(), case=False, na=False)]

    if df.empty:
        st.warning("No creators match your search.")
        return

    st.write(f"Showing **{len(df)}** creators")

    for _, row in df.iterrows():
        username = row.get("username") or "unknown"
        platform = row.get("platform") or ""
        followers = row.get("followers") or 0
        score = row.get("epic_trip_score")
        score_str = f"{score:.3f}" if score is not None else "N/A"
        niche = row.get("niche") or "—"
        ai_pass = row.get("ai_filter_pass")
        ai_icon = "✓" if ai_pass else ("✗" if ai_pass is False else "?")

        # Build profile URL
        if platform == "instagram":
            profile_url = f"https://www.instagram.com/{username}/"
        elif platform == "tiktok":
            profile_url = f"https://www.tiktok.com/@{username}"
        else:
            profile_url = "#"

        header = (
            f"**[@{username}]({profile_url})** | {platform.capitalize()} | "
            f"Followers: {followers:,} | Score: {score_str} | Niche: {niche} | AI: {ai_icon}"
        )

        with st.expander(header):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Profile info**")
                st.write(f"Bio: {row.get('bio') or '—'}")
                st.write(f"Location: {row.get('location') or '—'}")
                st.write(f"Posts (30d): {row.get('posts_last_30_days') or 0}")
                st.write(f"Avg engagement: {(row.get('avg_engagement') or 0):.3f}")
                st.write(f"AI reason: {row.get('ai_filter_reason') or '—'}")
                st.write(f"Status: {row.get('status') or '—'}")

            with col2:
                st.markdown("**Score Breakdown**")
                score_fields = {
                    "Engagement": row.get("score_engagement"),
                    "Niche": row.get("score_niche"),
                    "Followers": row.get("score_followers"),
                    "Growth": row.get("score_growth"),
                    "Activity": row.get("score_activity"),
                }
                for label, val in score_fields.items():
                    bar = int((val or 0) * 10)
                    bar_str = "█" * bar + "░" * (10 - bar)
                    st.write(f"{label:12s} {bar_str} {(val or 0):.2f}")

            # Recent posts
            post_rows = conn.execute(
                """SELECT post_id, post_type, published_at, likes, comments, views,
                          engagement_rate, caption, hashtags
                   FROM posts
                   WHERE creator_id = %s
                   ORDER BY published_at DESC
                   LIMIT 5""",
                (row["id"],),
            ).fetchall()

            if post_rows:
                st.markdown("**Recent Posts**")
                posts_data = []
                for p in post_rows:
                    hashtags_str = ""
                    try:
                        tags = json.loads(p["hashtags"] or "[]")
                        hashtags_str = " ".join(f"#{t}" for t in tags[:5])
                    except (json.JSONDecodeError, TypeError):
                        pass
                    posts_data.append({
                        "Type": p["post_type"],
                        "Date": (p["published_at"] or "")[:10],
                        "Likes": p["likes"] or 0,
                        "Comments": p["comments"] or 0,
                        "Views": p["views"] or 0,
                        "ER": f"{(p['engagement_rate'] or 0):.3f}",
                        "Caption": (p["caption"] or "")[:80],
                        "Hashtags": hashtags_str,
                    })
                posts_df = pd.DataFrame(posts_data)
                st.dataframe(posts_df, use_container_width=True)
