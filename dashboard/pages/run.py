from __future__ import annotations

import subprocess
from pathlib import Path

import streamlit as st

_VENV_PYTHON = str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "python")
_MAX_PROFILES = 200
_COST_DISCOVERY = 0.0010
_COST_PROFILE = 0.0026
_COST_POST    = 0.0023
_COST_AI      = 0.001


def _run_password() -> str:
    from config.settings import RUN_PASSWORD
    return RUN_PASSWORD


def _profile_url(username: str, platform: str) -> str:
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{username}"
    return f"https://www.instagram.com/{username}/"


def _step_label(n: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"<div style='display:flex;align-items:flex-start;gap:10px;margin-bottom:8px'>"
        f"<div style='background:#1d4ed8;color:#fff;border-radius:50%;min-width:28px;height:28px;"
        f"display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.8rem'>{n}</div>"
        f"<div><div style='font-weight:600;font-size:0.95rem;color:#f9fafb'>{title}</div>"
        f"<div style='font-size:0.75rem;color:#6b7280'>{subtitle}</div></div></div>",
        unsafe_allow_html=True,
    )


def render(conn) -> None:
    from db.repository import get_search_configs

    st.title("▶️ Pipeline")

    # ══════════════════════════════════════════════════════════════════════════
    # PASSO 1 — Seeds
    # ══════════════════════════════════════════════════════════════════════════
    with st.container(border=True):
        _step_label("1", "Seeds de busca", "Selecione a plataforma e as seeds que serão usadas na coleta")

        # ── Plataforma ──────────────────────────────────────────────────────
        platform = st.radio(
            "Plataforma",
            options=["instagram", "tiktok"],
            format_func=lambda x: "📷 Instagram" if x == "instagram" else "🎵 TikTok",
            horizontal=True,
            label_visibility="collapsed",
        )

        st.divider()

        # DB stats (used throughout)
        total   = conn.execute("SELECT COUNT(*) FROM creators WHERE platform=%s", (platform,)).fetchone()[0]
        excl    = conn.execute("SELECT COUNT(*) FROM creators WHERE platform=%s AND status='excluded'", (platform,)).fetchone()[0]
        active  = total - excl
        w_posts = conn.execute(
            "SELECT COUNT(DISTINCT c.id) FROM creators c JOIN posts p ON p.creator_id=c.id WHERE c.platform=%s",
            (platform,),
        ).fetchone()[0]
        ai_done = conn.execute(
            "SELECT COUNT(*) FROM creators WHERE platform=%s AND ai_filter_pass IS NOT NULL", (platform,)
        ).fetchone()[0]

        platform_seeds = get_search_configs(conn, platform=platform, active_only=True)

        selected_seed_ids: list[int] | None = None

        if not platform_seeds:
            st.warning("Nenhuma seed ativa. Configure em **🔍 Busca**.")
        else:
            all_tags: list[str] = []
            for s in platform_seeds:
                for t in s.get("tags", []):
                    if t not in all_tags:
                        all_tags.append(t)

            col_list, col_mode = st.columns([3, 2])

            with col_mode:
                sel_mode = st.radio(
                    "Usar",
                    options=["all", "by_tag", "manual"],
                    format_func=lambda x: {
                        "all":    f"Todas as ativas ({len(platform_seeds)})",
                        "by_tag": "Filtrar por tag",
                        "manual": "Selecionar manualmente",
                    }[x],
                    key=f"seed_mode_{platform}",
                )

                if sel_mode == "by_tag":
                    if all_tags:
                        chosen_tags = st.multiselect("Tags", all_tags, default=all_tags, key=f"stags_{platform}")
                        matched = [s for s in platform_seeds if any(t in s.get("tags", []) for t in chosen_tags)] if chosen_tags else []
                        selected_seed_ids = [s["id"] for s in matched] or None
                    else:
                        st.caption("Nenhuma seed tem tag. Configure em **Busca**.")
                elif sel_mode == "manual":
                    opts = {s["id"]: f"{s['search_type']}: {s['value']}" for s in platform_seeds}
                    chosen = st.multiselect("Seeds", list(opts.keys()), default=list(opts.keys()),
                                            format_func=lambda x: opts[x], key=f"sman_{platform}")
                    selected_seed_ids = chosen or None

            with col_list:
                visible = platform_seeds if selected_seed_ids is None else [s for s in platform_seeds if s["id"] in (selected_seed_ids or [])]
                st.caption(f"**{len(visible)} seed(s) selecionada(s)**")
                for s in visible[:6]:
                    tags_md = "  " + " ".join(f"`{t}`" for t in s.get("tags", [])) if s.get("tags") else ""
                    st.caption(f"· `{s['search_type']}` {s['value']}{tags_md}")
                if len(visible) > 6:
                    st.caption(f"  … e mais {len(visible) - 6}")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # PASSO 2 — Coletar perfis
    # ══════════════════════════════════════════════════════════════════════════
    with st.container(border=True):
        _step_label("2", "Coletar creators", "Scraping de perfis básicos: followers, bio, localização — sem posts")

        c_slider, c_stat = st.columns([3, 1])
        with c_slider:
            limit = st.slider(
                "Creators a buscar",
                min_value=10, max_value=_MAX_PROFILES, value=50, step=10,
                help="Cada perfil custa ~$0.0026 no Apify.",
            )
        with c_stat:
            st.metric("No banco", total, help=f"Creators já coletados para {platform}")

        est_discovery = limit * _COST_DISCOVERY
        est_profiles  = limit * _COST_PROFILE
        st.caption(
            f"Custo estimado desta etapa: **~${est_discovery + est_profiles:.2f}**"
            f"  _(discovery ~${est_discovery:.2f} + perfis ~${est_profiles:.2f})_"
        )

        st.divider()
        c_pwd2, c_btn2 = st.columns([3, 2])
        with c_pwd2:
            pwd2 = st.text_input(
                "Senha", type="password", key="collect_pwd",
                placeholder="Senha de confirmação", label_visibility="collapsed",
            )
        with c_btn2:
            collect_btn = st.button(
                "⬇️ Executar Coleta", key="collect_btn",
                type="primary", use_container_width=True, disabled=not pwd2,
            )

        if collect_btn:
            if pwd2 != _run_password():
                st.error("Senha incorreta.")
            else:
                collect_args = [
                    _VENV_PYTHON, "-m", "pipeline.runner",
                    "--platform", platform,
                    "--profiles-only",
                    "--limit", str(limit),
                ]
                if selected_seed_ids:
                    collect_args += ["--seed-ids", ",".join(str(i) for i in selected_seed_ids)]

                st.caption(f"`{' '.join(collect_args[2:])}`")
                ts_before = __import__("datetime").datetime.utcnow().isoformat()
                with st.spinner("Coletando perfis…"):
                    result = subprocess.run(
                        collect_args, capture_output=True, text=True, timeout=600,
                        cwd=str(Path(__file__).resolve().parents[2]),
                    )
                if result.returncode == 0:
                    st.success("✅ Coleta concluída!")
                    st.session_state[f"last_collect_ts_{platform}"] = ts_before
                else:
                    st.error(f"❌ Coleta falhou (código {result.returncode})")
                with st.expander("📋 Log", expanded=(result.returncode != 0)):
                    st.code(result.stdout + result.stderr, language="bash")

        # ── Tabela de creators coletados (salvos no banco local) ───────────
        import pandas as pd
        last_ts = st.session_state.get(f"last_collect_ts_{platform}")
        collected_query = (
            "SELECT id, username, display_name, followers, bio, email, category, status, is_lead "
            "FROM creators WHERE platform=%s AND first_seen_at >= %s ORDER BY first_seen_at DESC"
            if last_ts else
            "SELECT id, username, display_name, followers, bio, email, category, status, is_lead "
            "FROM creators WHERE platform=%s ORDER BY first_seen_at DESC LIMIT 50"
        )
        collected_params = (platform, last_ts) if last_ts else (platform,)
        collected_rows = conn.execute(collected_query, collected_params).fetchall()

        if collected_rows:
            label = f"Coletados nesta execução ({len(collected_rows)})" if last_ts else f"Últimos {len(collected_rows)} no banco"
            with st.expander(f"💾 {label} — salvos no banco local", expanded=bool(last_ts)):
                df_col = pd.DataFrame([dict(r) for r in collected_rows])
                df_col["Marcar"] = False
                df_col["⭐ Lead"] = df_col["is_lead"].astype(bool)
                df_col["bio_short"] = df_col["bio"].apply(lambda x: (x or "")[:60] + "…" if x and len(x) > 60 else (x or "—"))
                df_col["followers_fmt"] = df_col["followers"].apply(lambda x: f"{x:,}" if x else "—")

                df_col["Perfil"] = df_col["username"].apply(lambda u: _profile_url(u, platform))

                edited_col = st.data_editor(
                    df_col[["Marcar", "⭐ Lead", "Perfil", "display_name", "followers_fmt", "bio_short", "email", "category", "status"]].rename(columns={
                        "display_name": "Nome", "followers_fmt": "Followers",
                        "bio_short": "Bio", "email": "Email", "category": "Categoria", "status": "Status",
                    }),
                    column_config={
                        "Marcar": st.column_config.CheckboxColumn("Marcar", default=False),
                        "⭐ Lead": st.column_config.CheckboxColumn("⭐ Lead", help="Lead boa — salvo no banco", disabled=True),
                        "Perfil": st.column_config.LinkColumn("Perfil", display_text=r"https://(?:www\.)?(?:instagram\.com|tiktok\.com)/@?(\w+)/?$"),
                    },
                    disabled=["⭐ Lead", "Perfil", "Nome", "Followers", "Bio", "Email", "Categoria", "Status"],
                    use_container_width=True, hide_index=True,
                    key="collected_editor",
                )

                sel_col = edited_col[edited_col["Marcar"]].index.tolist()
                if sel_col:
                    c_lead1, c_lead2 = st.columns(2)
                    with c_lead1:
                        if st.button(f"⭐ Marcar {len(sel_col)} como lead boa", key="col_lead_btn", use_container_width=True):
                            ids = [int(df_col.loc[i, "id"]) for i in sel_col]
                            from db.repository import set_creator_lead
                            set_creator_lead(conn, ids, is_lead=True)
                            st.success(f"⭐ {len(ids)} creator(s) marcado(s) como lead!")
                            st.rerun()
                    with c_lead2:
                        if st.button(f"✖ Remover lead de {len(sel_col)}", key="col_unlead_btn", use_container_width=True, type="secondary"):
                            ids = [int(df_col.loc[i, "id"]) for i in sel_col]
                            from db.repository import set_creator_lead
                            set_creator_lead(conn, ids, is_lead=False)
                            st.success(f"Lead removida de {len(ids)} creator(s).")
                            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # PASSO 3 — Filtro inicial (editável)
    # ══════════════════════════════════════════════════════════════════════════
    with st.container(border=True):
        _step_label("3", "Filtro inicial", "Edite os critérios e veja quantos passam — sem custo")

        from config.filters import EXCLUDED_KEYWORDS, INSTAGRAM, TIKTOK

        # ── Plataforma(s) do filtro ────────────────────────────────────────
        plat_options = ["instagram", "tiktok"]
        plat_labels  = {"instagram": "📷 Instagram", "tiktok": "🎵 TikTok"}
        filt_platforms = st.multiselect(
            "Plataformas",
            options=plat_options,
            default=[platform],
            format_func=lambda x: plat_labels[x],
            key=f"filt_platforms_{platform}",
            help="Escolha uma ou ambas as plataformas para aplicar o filtro.",
        )
        if not filt_platforms:
            filt_platforms = [platform]

        thr = INSTAGRAM if "instagram" in filt_platforms else TIKTOK
        def_min = thr.get("min_followers", 0)

        # ── Followers ──────────────────────────────────────────────────────
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            filt_min_f = st.number_input(
                "Followers mínimos", min_value=0, max_value=10_000_000,
                value=def_min, step=100, key=f"filt_min_{platform}",
                help="Exclui contas com menos seguidores do que esse valor.",
            )
        with c_f2:
            filt_ratio = st.number_input(
                "Ratio followers/following mínimo", min_value=0.0, max_value=500.0,
                value=0.0, step=0.5, format="%.1f", key=f"filt_ratio_{platform}",
                help="Exclui contas onde (seguidores ÷ seguindo) é menor que esse valor. 0 = sem filtro.",
            )

        # ── Checkboxes ─────────────────────────────────────────────────────
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            filt_excl_business = st.checkbox(
                "Excluir contas business",
                value=False,
                key=f"filt_biz_{platform}",
                help="Exclui perfis marcados como 'conta comercial' no Instagram/TikTok. Creators autênticos geralmente usam conta pessoal.",
            )
        with c_b2:
            filt_require_email = st.checkbox(
                "Exigir email público",
                value=False,
                key=f"filt_email_{platform}",
                help="Mantém apenas creators que expõem um email no perfil — sinal de que estão ativamente abertos a parcerias e colaborações.",
            )

        # ── Categorias excluídas (Instagram only) ──────────────────────────
        if platform == "instagram":
            cat_input = st.text_input(
                "Categorias excluídas (Instagram)",
                value="",
                key=f"filt_cat_{platform}",
                placeholder="ex: Travel Agency, Hotel, Brand",
                help="Categoria de negócio do perfil no Instagram (campo 'category'). Liste categorias a excluir, separadas por vírgula. Ex: 'Travel Agency, Hotel, Resort, Tour Operator'.",
            )
            filt_excl_cats = [c.strip() for c in cat_input.split(",") if c.strip()]
        else:
            filt_excl_cats = []

        # ── Keywords excluídas na bio ───────────────────────────────────────
        kw_input = st.text_area(
            "Keywords excluídas na bio",
            value="",
            height=90,
            key=f"filt_kw_{platform}",
            placeholder="ex: agency, hotel, brand, resort — separadas por vírgula",
            help="Se qualquer uma dessas palavras aparecer na bio do creator, ele é excluído. Separadas por vírgula. Deixe em branco para não filtrar.",
        )
        filt_keywords = [k.strip() for k in kw_input.split(",") if k.strip()]

        # ── Escopo do filtro ───────────────────────────────────────────────
        last_ts_f = st.session_state.get(f"last_collect_ts_{platform}")
        if last_ts_f:
            scope_options = ["Apenas desta coleta (Passo 2)", "Banco completo (exceto excluded / contacted / deleted)"]
            scope_key = f"filt_scope_with_collect_{platform}"
        else:
            scope_options = ["Banco completo (exceto excluded / contacted / deleted)"]
            scope_key = f"filt_scope_no_collect_{platform}"
        scope = st.radio(
            "Aplicar filtro sobre",
            scope_options,
            key=scope_key,
            horizontal=True,
            help="'Desta coleta' usa somente os perfis coletados agora. 'Banco completo' inclui tudo que já foi coletado, ignorando apenas os já excluídos, contatados ou deletados.",
        )

        # ── Preview ao vivo ────────────────────────────────────────────────
        plat_placeholders = ",".join(["%s"] * len(filt_platforms))
        if last_ts_f and scope == "Apenas desta coleta (Passo 2)":
            all_profiles = conn.execute(
                f"SELECT id, username, display_name, followers, following, is_private, bio, "
                f"business_account, total_posts, email, category FROM creators "
                f"WHERE platform IN ({plat_placeholders}) AND status != 'excluded' AND first_seen_at >= %s",
                (*filt_platforms, last_ts_f),
            ).fetchall()
        else:
            all_profiles = conn.execute(
                f"SELECT id, username, display_name, followers, following, is_private, bio, "
                f"business_account, total_posts, email, category FROM creators "
                f"WHERE platform IN ({plat_placeholders}) AND status NOT IN ('excluded', 'contacted', 'deleted')",
                tuple(filt_platforms),
            ).fetchall()

        if all_profiles:
            passed_rows = []
            for row in all_profiles:
                if row["is_private"]:
                    continue
                f = row["followers"]
                if f is not None and f < filt_min_f:
                    continue
                bio_lower = (row["bio"] or "").lower()
                if any(kw.lower() in bio_lower for kw in filt_keywords):
                    continue
                if filt_excl_business and row["business_account"]:
                    continue
                if filt_ratio > 0.0:
                    following = row["following"] or 0
                    followers = row["followers"] or 0
                    if following > 0 and (followers / following) < filt_ratio:
                        continue
                if filt_require_email and not (row["email"] or "").strip():
                    continue
                if filt_excl_cats:
                    cat_lower = (row["category"] or "").lower()
                    if any(ec.lower() in cat_lower for ec in filt_excl_cats):
                        continue
                passed_rows.append(dict(row))
            preview_pass = len(passed_rows)

            c_prev, c_info = st.columns([1, 3])
            with c_prev:
                st.metric("Passariam", preview_pass, delta=f"de {len(all_profiles)} no banco")
            with c_info:
                st.markdown(
                    f"<div style='font-size:0.78rem;color:#9ca3af;margin-top:10px'>"
                    f"🔒 Contas privadas sempre excluídas &nbsp;·&nbsp; "
                    f"{len(all_profiles) - preview_pass} seriam excluídos"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            if passed_rows:
                with st.expander(f"👥 Creators que passariam ({preview_pass})", expanded=False):
                    df_preview = pd.DataFrame(passed_rows)
                    df_preview["Followers"] = df_preview["followers"].apply(lambda x: f"{x:,}" if x else "—")
                    df_preview["bio_short"] = df_preview["bio"].apply(lambda x: (x or "")[:60] + "…" if x and len(x) > 60 else (x or "—"))
                    df_preview["Perfil"] = df_preview["username"].apply(lambda u: _profile_url(u, platform))
                    st.dataframe(
                        df_preview[["Perfil", "display_name", "Followers", "category", "bio_short", "email"]].rename(columns={
                            "display_name": "Nome",
                            "category": "Categoria",
                            "bio_short": "Bio",
                            "email": "Email",
                        }),
                        column_config={
                            "Perfil": st.column_config.LinkColumn("Perfil", display_text=r"https://(?:www\.)?(?:instagram\.com|tiktok\.com)/@?(\w+)/?$"),
                        },
                        use_container_width=True,
                        hide_index=True,
                    )
        else:
            filt_min_f = def_min
            filt_keywords = []
            filt_ratio = 0.0
            filt_excl_business = False
            filt_require_email = False
            filt_excl_cats = []
            preview_pass = 0
            passed_rows = []
            st.caption("Nenhum creator no banco ainda — colete perfis primeiro (Step 2).")

    # ══════════════════════════════════════════════════════════════════════════
    # PASSO 4 — Scrapar posts
    # ══════════════════════════════════════════════════════════════════════════
    with st.container(border=True):
        _step_label("4", "Scrapar posts", "Busca posts/vídeos dos creators — etapa mais cara")

        # Creators que passaram no filtro E ainda não têm posts
        filtered_ids = [r["id"] for r in passed_rows] if passed_rows else []
        if filtered_ids:
            id_placeholders = ",".join(["%s"] * len(filtered_ids))
            without_posts = conn.execute(
                f"SELECT COUNT(*) FROM creators c "
                f"WHERE c.id IN ({id_placeholders}) "
                f"AND NOT EXISTS (SELECT 1 FROM posts p WHERE p.creator_id = c.id)",
                tuple(filtered_ids),
            ).fetchone()[0]
        else:
            without_posts = 0

        c_s1, c_s2, c_stat2a, c_stat2b = st.columns([2, 2, 1, 1])
        with c_s1:
            max_scrape = st.slider(
                "Cap de creators",
                min_value=5, max_value=_MAX_PROFILES, value=30, step=5,
                help="Limite de custo: só esses terão posts scrapados por execução.",
            )
        with c_s2:
            max_posts = st.slider(
                "Posts por creator",
                min_value=5, max_value=50, value=30, step=5,
                help="Quantos posts/vídeos buscar por creator.",
            )
        with c_stat2a:
            st.metric("Filtrados sem posts", without_posts, help="Passaram no filtro e ainda não têm posts")
        with c_stat2b:
            st.metric("Com posts", w_posts, help="Já têm posts no banco")

        will_scrape = min(without_posts, max_scrape)
        if without_posts > 0:
            capped = without_posts > max_scrape
            color  = "#f59e0b" if capped else "#22c55e"
            label  = (
                f"<b>{without_posts}</b> filtrados sem posts → cap em <b>{max_scrape}</b> → scrapa <b>{will_scrape}</b>"
                if capped else
                f"<b>{without_posts}</b> filtrados sem posts → scrapa todos os <b>{will_scrape}</b>"
            )
            st.markdown(
                f"<div style='font-size:0.8rem;color:{color};margin-bottom:4px'>{label}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='font-size:0.8rem;color:#22c55e;margin-bottom:4px'>✅ Todos os creators filtrados já têm posts coletados</div>",
                unsafe_allow_html=True,
            )

        effective = will_scrape if without_posts > 0 else max_scrape
        st.caption(f"Custo estimado: **~${effective * max_posts * _COST_POST:.2f}** ({effective} × {max_posts} posts × $0.0023)")

        st.divider()

        def _build_scrape_args(skip_with_posts: bool) -> list[str]:
            args = [
                _VENV_PYTHON, "-m", "pipeline.runner",
                "--platform", platform,
                "--scrape-only",
                "--max-scrape", str(max_scrape),
                "--max-posts",  str(max_posts),
                "--min-followers", str(int(filt_min_f)),
            ]
            if skip_with_posts:
                args += ["--skip-with-posts"]
            if selected_seed_ids:
                args += ["--seed-ids", ",".join(str(i) for i in selected_seed_ids)]
            if filt_keywords:
                args += ["--excluded-keywords", "|".join(filt_keywords)]
            if filt_excl_business:
                args += ["--exclude-business"]
            if filt_ratio > 0.0:
                args += ["--min-follower-ratio", str(filt_ratio)]
            if filt_require_email:
                args += ["--require-email"]
            if filt_excl_cats:
                args += ["--excluded-categories", "|".join(filt_excl_cats)]
            return args

        pwd4 = st.text_input(
            "Senha", type="password", key="scrape_posts_pwd",
            placeholder="Senha de confirmação", label_visibility="collapsed",
        )

        c_btn_new, c_btn_all = st.columns(2)
        with c_btn_new:
            scrape_new_btn = st.button(
                f"📥 Scrapar filtrados novos ({without_posts})",
                key="scrape_new_btn",
                type="primary", use_container_width=True,
                disabled=not pwd4 or without_posts == 0,
            )
        with c_btn_all:
            scrape_all_btn = st.button(
                f"🔄 Atualizar posts dos filtrados ({preview_pass} filtrados)",
                key="scrape_all_btn",
                type="secondary", use_container_width=True,
                disabled=not pwd4 or preview_pass == 0,
            )

        for btn, skip in [(scrape_new_btn, True), (scrape_all_btn, False)]:
            if btn:
                if pwd4 != _run_password():
                    st.error("Senha incorreta.")
                else:
                    scrape_args = _build_scrape_args(skip_with_posts=skip)
                    label_run = "novos creators" if skip else "todos os creators"
                    st.caption(f"`{' '.join(scrape_args[2:])}`")
                    with st.spinner(f"Scrapando posts de {label_run}…"):
                        result = subprocess.run(
                            scrape_args, capture_output=True, text=True, timeout=1200,
                            cwd=str(Path(__file__).resolve().parents[2]),
                        )
                    if result.returncode == 0:
                        st.success(f"✅ Posts scrapados ({label_run})!")
                    else:
                        st.error(f"❌ Falhou (código {result.returncode})")
                    with st.expander("📋 Log", expanded=(result.returncode != 0)):
                        st.code(result.stdout + result.stderr, language="bash")

    # ── Creators com posts ──────────────────────────────────────────────────
    import pandas as pd
    from datetime import datetime, timezone

    scraped_rows = conn.execute(
        """
        SELECT c.id, c.username, c.display_name, c.followers, c.niche,
               c.email, c.link_in_bio, c.avg_engagement, c.posts_last_30_days,
               c.bio, c.category, c.status,
               COUNT(p.id) AS post_count,
               MAX(o.contacted_at) AS contacted_at
        FROM creators c
        JOIN posts p ON p.creator_id = c.id
        LEFT JOIN outreach o ON o.creator_id = c.id
        WHERE c.platform = %s AND c.status != 'excluded'
        GROUP BY c.id
        ORDER BY c.followers DESC
        """,
        (platform,),
    ).fetchall()

    if scraped_rows:
        df_scraped = pd.DataFrame([dict(r) for r in scraped_rows])

        df_scraped["Eng."]      = df_scraped["avg_engagement"].apply(lambda x: f"{x*100:.1f}%" if x is not None else "—")
        df_scraped["Posts/30d"] = df_scraped["posts_last_30_days"].fillna("—")
        df_scraped["Followers"] = df_scraped["followers"].apply(lambda x: f"{x:,}" if x is not None else "—")
        df_scraped["Contatado"] = df_scraped["contacted_at"].notna()
        df_scraped["Marcar"]    = False
        df_scraped["bio_short"] = df_scraped["bio"].apply(lambda x: (x or "")[:60] + "…" if x and len(x) > 60 else (x or "—"))

        c_title4, c_dl4 = st.columns([4, 1])
        with c_title4:
            st.markdown(
                f"#### Creators com posts  <span style='font-size:0.8rem;color:#6b7280;font-weight:400'>({len(scraped_rows)})</span>",
                unsafe_allow_html=True,
            )
        with c_dl4:
            csv_scraped = df_scraped[["username", "display_name", "followers", "category", "niche",
                                      "email", "link_in_bio", "bio", "avg_engagement",
                                      "posts_last_30_days", "post_count", "status"]].copy()
            csv_scraped.columns = ["username", "display_name", "followers", "category", "niche",
                                   "email", "link_in_bio", "bio", "avg_engagement",
                                   "posts_last_30d", "post_count", "status"]
            st.download_button(
                "⬇️ Exportar CSV",
                csv_scraped.to_csv(index=False),
                file_name=f"creators_posts_{platform}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        df_scraped["Perfil"] = df_scraped["username"].apply(lambda u: _profile_url(u, platform))

        display_scraped = df_scraped[["Marcar", "Perfil", "display_name", "Followers", "category", "niche",
                                      "bio_short", "Eng.", "Posts/30d", "post_count", "email", "Contatado"]].rename(columns={
            "display_name": "Nome",
            "category":     "Categoria",
            "niche":        "Nicho",
            "bio_short":    "Bio",
            "post_count":   "Posts scrapados",
            "email":        "Email",
        })

        edited_scraped = st.data_editor(
            display_scraped,
            column_config={
                "Marcar": st.column_config.CheckboxColumn("Marcar", default=False),
                "Contatado": st.column_config.CheckboxColumn("✉️", disabled=True),
                "Perfil": st.column_config.LinkColumn("Perfil", display_text=r"https://(?:www\.)?(?:instagram\.com|tiktok\.com)/@?(\w+)/?$"),
                "Followers":       st.column_config.TextColumn("Followers",       width="small"),
                "Eng.":            st.column_config.TextColumn("Eng.",            width="small"),
                "Posts/30d":       st.column_config.TextColumn("Posts/30d",       width="small"),
                "Posts scrapados": st.column_config.TextColumn("Posts scrapados", width="small"),
            },
            disabled=["Perfil", "Nome", "Followers", "Categoria", "Nicho", "Bio", "Eng.", "Posts/30d", "Posts scrapados", "Email", "Contatado"],
            use_container_width=True,
            hide_index=True,
            key="scraped_editor",
        )

        marked4 = edited_scraped[edited_scraped["Marcar"]].index.tolist()
        if marked4:
            if st.button(
                f"💌 Marcar {len(marked4)} creator(s) como contatado(s)",
                type="primary",
                key="mark_scraped_btn",
            ):
                now = datetime.now(timezone.utc).isoformat()
                for idx in marked4:
                    cid = int(df_scraped.loc[idx, "id"])
                    conn.execute(
                        "INSERT INTO outreach (creator_id, contacted_at, status) VALUES (%s, %s, %s)",
                        (cid, now, "contacted"),
                    )
                conn.commit()
                st.success(f"✅ {len(marked4)} creator(s) marcado(s) como contatado(s)!")
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # PASSO 5 — AI Filter & Score
    # ══════════════════════════════════════════════════════════════════════════
    with st.container(border=True):
        _step_label("5", "AI Filter & Score", "A IA avalia cada creator com base no critério abaixo e gera um score final")

        from pipeline.ai_filter import _DEFAULT_CRITERIA
        ai_criteria_input = st.text_area(
            "Critério de avaliação",
            value=_DEFAULT_CRITERIA,
            height=160,
            key="ai_criteria",
            help=(
                "Descreva o perfil ideal de creator. A IA vai ler bio, nicho, captions e hashtags "
                "de cada pessoa e decidir se passa ou não com base nesse texto. "
                "A instrução de formato JSON é adicionada automaticamente."
            ),
        )

        c_ai, c_ai_stat = st.columns([3, 1])
        with c_ai:
            max_ai = st.slider(
                "Máx. avaliações GPT",
                min_value=5, max_value=_MAX_PROFILES, value=30, step=5,
                help="Controle de custo: quantos creators enviar ao AI filter por execução.",
            )
        with c_ai_stat:
            st.metric("Avaliados", ai_done)

        st.caption(f"Custo estimado: **~${max_ai * _COST_AI:.2f}**")

        st.divider()
        c_pwd5, c_btn5 = st.columns([3, 2])
        with c_pwd5:
            pwd5 = st.text_input(
                "Senha", type="password", key="ai_pwd",
                placeholder="Senha de confirmação", label_visibility="collapsed",
            )
        with c_btn5:
            ai_btn = st.button(
                "🤖 Executar AI Filter", key="ai_run_btn",
                type="primary", use_container_width=True, disabled=not pwd5,
            )

        if ai_btn:
            if pwd5 != _run_password():
                st.error("Senha incorreta.")
            else:
                ai_args = [
                    _VENV_PYTHON, "-m", "pipeline.runner",
                    "--platform", platform,
                    "--skip-scrape",
                    "--max-ai-filter", str(max_ai),
                ]
                from pipeline.ai_filter import _DEFAULT_CRITERIA as _DEF_CRIT
                if ai_criteria_input.strip() != _DEF_CRIT.strip():
                    ai_args += ["--ai-criteria", ai_criteria_input.strip()]

                st.caption(f"`{' '.join(ai_args[2:])}`")
                with st.spinner("Rodando AI filter…"):
                    result = subprocess.run(
                        ai_args, capture_output=True, text=True, timeout=900,
                        cwd=str(Path(__file__).resolve().parents[2]),
                    )
                if result.returncode == 0:
                    st.success("✅ AI Filter concluído!")
                else:
                    st.error(f"❌ Falhou (código {result.returncode})")
                with st.expander("📋 Log", expanded=(result.returncode != 0)):
                    st.code(result.stdout + result.stderr, language="bash")

    # ══════════════════════════════════════════════════════════════════════════
    # RESULTADOS
    # ══════════════════════════════════════════════════════════════════════════
    st.divider()

    result_rows = conn.execute(
        """
        SELECT c.id, c.username, c.display_name, c.followers, c.niche,
               c.email, c.link_in_bio,
               c.ai_filter_pass, c.ai_filter_reason,
               c.epic_trip_score, c.avg_engagement, c.posts_last_30_days,
               c.is_lead,
               MAX(o.contacted_at) AS contacted_at
        FROM creators c
        LEFT JOIN outreach o ON o.creator_id = c.id
        WHERE c.platform = %s AND c.ai_filter_pass IS NOT NULL AND c.status != 'deleted'
        GROUP BY c.id
        ORDER BY c.epic_trip_score DESC
        """,
        (platform,),
    ).fetchall()

    if result_rows:
        df = pd.DataFrame([dict(r) for r in result_rows])

        # ── Formatted display columns ──────────────────────────────────────
        df["Pass"]      = df["ai_filter_pass"].map({1: "✅", 0: "❌"})
        df["Score"]     = df["epic_trip_score"].apply(lambda x: f"{x:.2f}" if x is not None else "—")
        df["Eng."]      = df["avg_engagement"].apply(lambda x: f"{x*100:.1f}%" if x is not None else "—")
        df["Posts/30d"] = df["posts_last_30_days"].fillna("—")
        df["Followers"] = df["followers"].apply(lambda x: f"{x:,}" if x is not None else "—")
        df["Contatado"] = df["contacted_at"].notna()
        df["⭐ Lead"]   = df["is_lead"].astype(bool)
        df["Marcar"]    = False

        # ── Header + download ──────────────────────────────────────────────
        c_title, c_dl = st.columns([4, 1])
        with c_title:
            st.markdown(
                f"#### Resultados  <span style='font-size:0.8rem;color:#6b7280;font-weight:400'>({len(result_rows)} avaliados)</span>",
                unsafe_allow_html=True,
            )
        with c_dl:
            csv_df = df[["ai_filter_pass", "username", "display_name", "followers", "niche",
                         "email", "link_in_bio", "epic_trip_score", "avg_engagement",
                         "posts_last_30_days", "ai_filter_reason", "contacted_at"]].copy()
            csv_df.columns = ["pass", "username", "display_name", "followers", "niche",
                               "email", "link_in_bio", "score", "avg_engagement",
                               "posts_last_30d", "ai_reason", "contacted_at"]
            st.download_button(
                "⬇️ Exportar CSV",
                csv_df.to_csv(index=False),
                file_name=f"creators_{platform}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        # ── Editable results table ─────────────────────────────────────────
        df["Perfil"] = df["username"].apply(lambda u: _profile_url(u, platform))

        display_df = df[["Marcar", "⭐ Lead", "Pass", "Perfil", "Followers", "niche",
                          "Score", "Eng.", "Posts/30d", "ai_filter_reason", "Contatado"]].rename(columns={
            "niche": "Nicho",
            "ai_filter_reason": "Motivo IA",
        })

        edited_df = st.data_editor(
            display_df,
            column_config={
                "Marcar": st.column_config.CheckboxColumn(
                    "Marcar",
                    help="Selecione para ações em lote",
                    default=False,
                ),
                "⭐ Lead": st.column_config.CheckboxColumn(
                    "⭐ Lead",
                    help="Lead boa — marcado no banco",
                    disabled=True,
                ),
                "Contatado": st.column_config.CheckboxColumn(
                    "✉️",
                    help="Já contatado anteriormente",
                    disabled=True,
                ),
                "Perfil": st.column_config.LinkColumn("Perfil", display_text=r"https://(?:www\.)?(?:instagram\.com|tiktok\.com)/@?(\w+)/?$"),
                "Pass":      st.column_config.TextColumn("Pass",      width="small"),
                "Score":     st.column_config.TextColumn("Score",     width="small"),
                "Eng.":      st.column_config.TextColumn("Eng.",      width="small"),
                "Posts/30d": st.column_config.TextColumn("Posts/30d", width="small"),
            },
            disabled=["⭐ Lead", "Pass", "Perfil", "Followers", "Nicho", "Score", "Eng.", "Posts/30d", "Motivo IA", "Contatado"],
            use_container_width=True,
            hide_index=True,
            key="results_editor",
        )

        marked_indices = edited_df[edited_df["Marcar"]].index.tolist()
        if marked_indices:
            c_act1, c_act2, c_act3, c_act4 = st.columns(4)
            with c_act1:
                if st.button(
                    f"⭐ Lead boa ({len(marked_indices)})",
                    key="mark_lead_btn",
                    use_container_width=True,
                ):
                    from db.repository import set_creator_lead
                    ids = [int(df.loc[i, "id"]) for i in marked_indices]
                    set_creator_lead(conn, ids, is_lead=True)
                    st.success(f"⭐ {len(ids)} marcado(s) como lead boa!")
                    st.rerun()
            with c_act2:
                if st.button(
                    f"✖ Remover lead ({len(marked_indices)})",
                    key="remove_lead_btn",
                    type="secondary",
                    use_container_width=True,
                ):
                    from db.repository import set_creator_lead
                    ids = [int(df.loc[i, "id"]) for i in marked_indices]
                    set_creator_lead(conn, ids, is_lead=False)
                    st.success(f"Lead removida de {len(ids)} creator(s).")
                    st.rerun()
            with c_act3:
                if st.button(
                    f"💌 Contatado ({len(marked_indices)})",
                    type="primary",
                    key="mark_contacted_btn",
                    use_container_width=True,
                ):
                    now = datetime.now(timezone.utc).isoformat()
                    for idx in marked_indices:
                        cid = int(df.loc[idx, "id"])
                        conn.execute(
                            "INSERT INTO outreach (creator_id, contacted_at, status) VALUES (%s, %s, %s)",
                            (cid, now, "contacted"),
                        )
                        conn.execute(
                            "UPDATE creators SET status='contacted', last_updated_at=%s WHERE id=%s",
                            (now, cid),
                        )
                    conn.commit()
                    st.success(f"✅ {len(marked_indices)} creator(s) marcado(s) como contatado(s)!")
                    st.rerun()
            with c_act4:
                if st.button(
                    f"🗑️ Deletar ({len(marked_indices)})",
                    type="secondary",
                    key="mark_deleted_btn",
                    use_container_width=True,
                ):
                    now = datetime.now(timezone.utc).isoformat()
                    for idx in marked_indices:
                        cid = int(df.loc[idx, "id"])
                        conn.execute(
                            "UPDATE creators SET status='deleted', last_updated_at=%s WHERE id=%s",
                            (now, cid),
                        )
                    conn.commit()
                    st.success(f"🗑️ {len(marked_indices)} creator(s) deletado(s) — não aparecerão mais nos resultados.")
                    st.rerun()
    else:
        st.caption("Nenhum creator avaliado ainda — execute o AI Filter (Step 5).")

    # ── Histórico ──────────────────────────────────────────────────────────────
    st.divider()
    with st.expander("📜 Histórico de execuções"):
        runs = conn.execute(
            "SELECT platform, status, creators_found, creators_qualified, "
            "apify_cost_usd, openai_cost_usd, started_at, finished_at "
            "FROM pipeline_runs ORDER BY started_at DESC LIMIT 10"
        ).fetchall()
        if runs:
            df_runs = pd.DataFrame([dict(r) for r in runs])
            df_runs["started_at"]  = pd.to_datetime(df_runs["started_at"]).dt.strftime("%Y-%m-%d %H:%M")
            df_runs["finished_at"] = pd.to_datetime(df_runs["finished_at"]).dt.strftime("%Y-%m-%d %H:%M").fillna("—")
            df_runs.rename(columns={
                "platform": "Plataforma", "status": "Status",
                "creators_found": "Descobertos", "creators_qualified": "Qualificados",
                "apify_cost_usd": "Apify $", "openai_cost_usd": "OpenAI $",
                "started_at": "Início", "finished_at": "Fim",
            }, inplace=True)
            st.dataframe(df_runs, use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhuma execução ainda.")
