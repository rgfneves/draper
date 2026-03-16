from __future__ import annotations


def render(conn) -> None:
    import pandas as pd
    import streamlit as st

    st.title("📊 Dashboard")

    # ── Load data ──────────────────────────────────────────────────────────────
    creators_rows = conn.execute("SELECT * FROM creators").fetchall()
    runs_rows = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 10"
    ).fetchall()

    from db.repository import get_search_configs
    ig_seeds = get_search_configs(conn, platform="instagram", active_only=True)
    tt_seeds = get_search_configs(conn, platform="tiktok", active_only=True)

    df = pd.DataFrame([dict(r) for r in creators_rows]) if creators_rows else pd.DataFrame()
    total = len(creators_rows)
    qualified = int((df["ai_filter_pass"] == 1).sum()) if not df.empty and "ai_filter_pass" in df.columns else 0
    avg_score = df["epic_trip_score"].dropna().mean() if not df.empty and "epic_trip_score" in df.columns else 0.0
    last_run = str(runs_rows[0]["started_at"])[:10] if runs_rows else None
    last_status = runs_rows[0]["status"] if runs_rows else None

    # ── Process status bar ─────────────────────────────────────────────────────
    total_seeds = len(ig_seeds) + len(tt_seeds)
    step1_ok = total_seeds > 0
    step2_ok = bool(runs_rows)
    step3_ok = total > 0

    st.markdown("#### Status do pipeline")
    c1, c2, c3 = st.columns(3)

    with c1:
        if step1_ok:
            st.success(f"**1. Busca configurada** — {total_seeds} seed(s) ativa(s)")
        else:
            st.warning("**1. Busca** — Nenhuma seed ativa")
            st.caption("→ Vá para **🔍 Busca** para configurar.")

    with c2:
        if step2_ok:
            status_icon = "✅" if last_status == "completed" else "⚠️"
            st.success(f"**2. Pipeline executado** — {status_icon} {last_run}")
        else:
            st.warning("**2. Executar** — Nenhuma execução ainda")
            st.caption("→ Vá para **▶️ Executar** para rodar.")

    with c3:
        if step3_ok:
            st.success(f"**3. Resultados** — {total} creator(s) no banco")
        else:
            st.warning("**3. Resultados** — Banco vazio")
            st.caption("→ Execute o pipeline para popular.")

    st.divider()

    # ── KPIs ───────────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total creators", total)
    k2.metric("AI aprovados", qualified)
    k3.metric("Score médio", f"{avg_score:.2f}")
    k4.metric("Seeds ativas", total_seeds)
    k5.metric("Última run", last_run or "—")

    if df.empty:
        return

    st.divider()

    # ── Charts ─────────────────────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Distribuição EpicTripScore")
        score_data = df["epic_trip_score"].dropna()
        if not score_data.empty:
            import numpy as np
            hist, edges = np.histogram(score_data, bins=10, range=(0.0, 1.0))
            hist_df = pd.DataFrame({
                "score": [f"{e:.1f}–{edges[i+1]:.1f}" for i, e in enumerate(edges[:-1])],
                "creators": hist,
            })
            st.bar_chart(hist_df.set_index("score"))
        else:
            st.caption("Ainda sem scores calculados.")

    with col_right:
        st.subheader("Creators por plataforma")
        if "platform" in df.columns and not df.empty:
            plat_df = df["platform"].value_counts().reset_index()
            plat_df.columns = ["plataforma", "total"]
            st.bar_chart(plat_df.set_index("plataforma"))

        # Seeds breakdown
        st.markdown("**Seeds ativas por plataforma**")
        sc1, sc2 = st.columns(2)
        with sc1:
            st.metric("📷 Instagram", len(ig_seeds))
        with sc2:
            st.metric("🎵 TikTok", len(tt_seeds))

    st.divider()

    # ── Recent runs ────────────────────────────────────────────────────────────
    st.subheader("Últimas execuções")
    if runs_rows:
        runs_df = pd.DataFrame([dict(r) for r in runs_rows])
        runs_df["started_at"] = runs_df["started_at"].str[:16]
        runs_df["finished_at"] = runs_df["finished_at"].str[:16].fillna("—")
        show_cols = [
            "platform", "status", "creators_found", "creators_qualified",
            "apify_cost_usd", "openai_cost_usd", "started_at",
        ]
        show_cols = [c for c in show_cols if c in runs_df.columns]
        st.dataframe(runs_df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhuma execução registrada ainda.")
