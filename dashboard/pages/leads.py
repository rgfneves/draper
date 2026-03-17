from __future__ import annotations

# Status definitions — order matters (shown in selectbox)
STATUSES: dict[str, dict] = {
    "discovered":  {"label": "Descoberto",        "color": "#6b7280"},
    "reviewing":   {"label": "Em análise",         "color": "#3b82f6"},
    "contacted":   {"label": "Contato realizado",  "color": "#f59e0b"},
    "negotiating": {"label": "Em negociação",      "color": "#8b5cf6"},
    "approved":    {"label": "Aprovado",           "color": "#10b981"},
    "rejected":    {"label": "Descartado",         "color": "#ef4444"},
}
# pipeline-managed status — not settable manually
_PIPELINE_STATUSES = {"excluded"}


def _status_badge(status: str) -> str:
    s = STATUSES.get(status)
    if s:
        return f"<span style='background:{s['color']};color:#fff;padding:2px 8px;" \
               f"border-radius:10px;font-size:0.75rem'>{s['label']}</span>"
    return f"<span style='background:#374151;color:#fff;padding:2px 8px;" \
           f"border-radius:10px;font-size:0.75rem'>{status or '—'}</span>"


def render(conn) -> None:
    import pandas as pd
    import streamlit as st

    from dashboard.components.export import download_csv_button
    from db.repository import bulk_update_creator_status

    st.title("🎯 Leads")

    rows = conn.execute(
        "SELECT * FROM creators WHERE status != 'excluded' ORDER BY epic_trip_score DESC NULLS LAST"
    ).fetchall()
    if not rows:
        st.info("Nenhum creator no banco ainda. Rode o pipeline primeiro.")
        return

    df = pd.DataFrame([dict(r) for r in rows])

    # ── Sidebar filters ────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Filtros")

        platforms = st.multiselect(
            "Plataforma", ["instagram", "tiktok"],
            default=["instagram", "tiktok"],
        )

        followers_min, followers_max = st.slider(
            "Seguidores", 0, 100_000, (0, 100_000), step=500,
        )

        score_min = st.slider(
            "EpicTripScore mínimo", 0.0, 1.0, 0.0, step=0.05,
        )

        ai_only = st.checkbox("Apenas AI approved", value=False)

        status_opts = [s for s in STATUSES if s not in _PIPELINE_STATUSES]
        status_filter = st.multiselect(
            "Status", status_opts,
            format_func=lambda s: STATUSES[s]["label"],
            default=status_opts,
        )

    # ── Apply filters ──────────────────────────────────────────────────────────
    total_before_filter = len(df)

    if platforms:
        df = df[df["platform"].isin(platforms)]
    df = df[df["followers"].fillna(0).between(followers_min, followers_max)]
    df = df[df["epic_trip_score"].fillna(0) >= score_min]
    if ai_only:
        df = df[df["ai_filter_pass"] == True]  # noqa: E712
    df = df[df["status"].isin(status_filter)] if status_filter else df.iloc[0:0]

    if df.empty and total_before_filter > 0:
        st.warning(
            f"{total_before_filter} creator(s) no banco, mas nenhum passa nos filtros atuais. "
            "Ajuste os filtros na barra lateral."
        )
        return

    # ── KPI bar ────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Leads filtrados", len(df))
    k2.metric("AI aprovados", int(df["ai_filter_pass"].sum()) if "ai_filter_pass" in df.columns else 0)
    avg = df["epic_trip_score"].dropna().mean() if not df.empty else 0
    k3.metric("Score médio", f"{avg:.2f}")
    top = df["epic_trip_score"].dropna().max() if not df.empty else 0
    k4.metric("Maior score", f"{top:.2f}")

    st.divider()

    # ── Table with row selection ───────────────────────────────────────────────
    display_cols = [c for c in [
        "username", "platform", "followers", "avg_engagement",
        "epic_trip_score", "niche", "ai_filter_pass", "status",
        "discovered_via_type", "discovered_via_value", "email",
    ] if c in df.columns]

    col_labels = {
        "username": "Username",
        "platform": "Plataforma",
        "followers": "Seguidores",
        "avg_engagement": "Eng. médio",
        "epic_trip_score": "Score",
        "niche": "Nicho",
        "ai_filter_pass": "AI ✓",
        "status": "Status",
        "discovered_via_type": "Via tipo",
        "discovered_via_value": "Via valor",
        "email": "Email",
    }

    display_df = df[display_cols].copy().rename(columns=col_labels)
    if "AI ✓" in display_df.columns:
        display_df["AI ✓"] = display_df["AI ✓"].map(
            {True: "✅ Pass", False: "❌ Fail"}
        ).fillna("—")

    selection = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
    )

    selected_indices = selection.selection.rows  # list of positional indices in display_df
    selected_ids = df.iloc[selected_indices]["id"].tolist() if selected_indices else []

    # ── Status update panel ────────────────────────────────────────────────────
    st.markdown("#### Atualizar status")

    action_col, all_col = st.columns([3, 2])

    with action_col:
        new_status = st.selectbox(
            "Novo status",
            options=list(STATUSES.keys()),
            format_func=lambda s: STATUSES[s]["label"],
            label_visibility="collapsed",
        )

    with all_col:
        apply_all = st.button(
            f"Aplicar a todos os {len(df)} filtrados",
            use_container_width=True,
            type="secondary",
        )

    apply_selected = st.button(
        f"Aplicar aos {len(selected_ids)} selecionados",
        disabled=(len(selected_ids) == 0),
        type="primary",
        use_container_width=True,
    )

    if apply_all:
        ids = df["id"].tolist()
        n = bulk_update_creator_status(conn, ids, new_status)
        label = STATUSES[new_status]["label"]
        st.success(f"✅ {n} creator(s) marcados como **{label}**.")
        st.rerun()

    if apply_selected:
        n = bulk_update_creator_status(conn, selected_ids, new_status)
        label = STATUSES[new_status]["label"]
        st.success(f"✅ {n} creator(s) marcados como **{label}**.")
        st.rerun()

    st.divider()

    # ── Status breakdown ───────────────────────────────────────────────────────
    if "status" in df.columns:
        breakdown = df["status"].value_counts().reset_index()
        breakdown.columns = ["status", "count"]
        breakdown["label"] = breakdown["status"].map(
            lambda s: STATUSES.get(s, {}).get("label", s)
        )
        cols = st.columns(min(len(breakdown), 6))
        for col, (_, row) in zip(cols, breakdown.iterrows()):
            color = STATUSES.get(row["status"], {}).get("color", "#6b7280")
            col.markdown(
                f"<div style='border-left:3px solid {color};padding-left:8px'>"
                f"<div style='font-size:1.4rem;font-weight:700'>{row['count']}</div>"
                f"<div style='font-size:0.75rem;color:#9ca3af'>{row['label']}</div></div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Export CSV completo (todas as colunas + agregados de posts + outreach) ──
    export_ids = df["id"].tolist() if "id" in df.columns and not df.empty else []

    if export_ids:
        placeholders = ",".join(["%s"] * len(export_ids))
        export_rows = conn.execute(
            f"""
            SELECT
                c.platform,
                c.username,
                c.display_name,
                c.followers,
                c.following,
                c.total_posts,
                c.bio,
                c.email,
                c.link_in_bio,
                c.category,
                c.location,
                c.verified,
                c.business_account,
                c.niche,
                c.ai_filter_pass,
                c.ai_filter_reason,
                c.epic_trip_score,
                c.score_engagement,
                c.score_niche,
                c.score_followers,
                c.score_growth,
                c.score_activity,
                c.avg_engagement,
                c.posts_last_30_days,
                c.posting_frequency,
                c.is_active,
                c.is_lead,
                c.status,
                c.discovered_via_type,
                c.discovered_via_value,
                c.first_seen_at,
                c.last_updated_at,
                o.last_contacted_at,
                COUNT(p.id)              AS posts_scraped_total,
                MAX(p.published_at)      AS last_post_date,
                AVG(p.likes)             AS avg_likes,
                AVG(p.comments)          AS avg_comments,
                AVG(p.views)             AS avg_views,
                AVG(p.engagement_rate)   AS avg_post_er,
                string_agg(
                    CASE WHEN p.caption IS NOT NULL
                         THEN left(p.caption, 150) END,
                    ' | '
                    ORDER BY p.published_at DESC
                ) FILTER (WHERE p.caption IS NOT NULL) AS sample_captions
            FROM creators c
            LEFT JOIN posts p ON p.creator_id = c.id
            LEFT JOIN (
                SELECT creator_id, MAX(contacted_at) AS last_contacted_at
                FROM outreach GROUP BY creator_id
            ) o ON o.creator_id = c.id
            WHERE c.id IN ({placeholders})
            GROUP BY c.id, o.last_contacted_at
            ORDER BY c.epic_trip_score DESC NULLS LAST
            """,
            export_ids,
        ).fetchall()

        export_df = pd.DataFrame([dict(r) for r in export_rows])
        if not export_df.empty and "ai_filter_pass" in export_df.columns:
            export_df["ai_filter_pass"] = export_df["ai_filter_pass"].map(
                {True: "pass", False: "fail"}
            ).fillna("not_evaluated")

    else:
        export_df = pd.DataFrame()

    platform_tag = df["platform"].iloc[0] if not df.empty and "platform" in df.columns else "leads"
    download_csv_button(
        export_df,
        filename=f"draper_{platform_tag}_export.csv",
        label=f"⬇️ Exportar CSV completo ({len(export_df)} creators)",
    )
