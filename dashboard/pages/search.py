from __future__ import annotations

import streamlit as st

METHODS = {
    "instagram": [
        {
            "search_type": "hashtag",
            "label": "Hashtag",
            "actor": "apify/instagram-hashtag-scraper",
            "description": "Posts com essa hashtag → extrai autores.",
            "placeholder": "ex: mochilero",
        },
        {
            "search_type": "location",
            "label": "Localização",
            "actor": "apidojo/instagram-location-scraper",
            "description": "Posts marcados nessa cidade/região → autores locais.",
            "placeholder": "ex: New York, London, Berlin",
        },
    ],
    "tiktok": [
        {
            "search_type": "hashtag",
            "label": "Hashtag",
            "actor": "clockworks/tiktok-scraper",
            "description": "Vídeos com essa hashtag → extrai criadores.",
            "placeholder": "ex: mochilero",
        },
        {
            "search_type": "keyword_search",
            "label": "Keyword Search",
            "actor": "clockworks/tiktok-user-search-scraper",
            "description": "Busca texto livre → retorna perfis diretamente.",
            "placeholder": "ex: mochileiro brasil viagem",
        },
        {
            "search_type": "country_code",
            "label": "País (filtro)",
            "actor": "apidojo/tiktok-scraper",
            "description": "Combina com as hashtags ativas e filtra por país do criador.",
            "placeholder": "ex: US, GB, DE, FR, CA",
        },
    ],
}

SOURCE_BADGE = {"manual": "🖊️ Manual", "ai": "🤖 AI"}


def render(conn) -> None:
    st.title("🔍 Busca")
    st.caption(
        "Configure **o que** o pipeline vai buscar. "
        "Cada seed ativa gera chamadas ao Apify — quantidade = custo. "
        "Quando estiver pronto, vá para **▶️ Executar**."
    )

    tab_ig, tab_tt = st.tabs(["📷 Instagram", "🎵 TikTok"])
    for tab, platform in zip([tab_ig, tab_tt], ["instagram", "tiktok"]):
        with tab:
            _render_platform(conn, platform)


def _render_platform(conn, platform: str) -> None:
    from db.repository import (
        delete_search_config,
        get_search_configs,
        toggle_search_config,
        upsert_search_config,
    )

    all_configs = get_search_configs(conn, platform=platform, active_only=False)
    total_active = sum(1 for c in all_configs if c["active"])

    st.markdown(
        f"**{total_active}** seed(s) ativa(s) · "
        f"**{len(all_configs)}** total configuradas"
    )
    st.divider()

    for method in METHODS[platform]:
        search_type = method["search_type"]
        configs = [c for c in all_configs if c["search_type"] == search_type]
        active_count = sum(1 for c in configs if c["active"])

        col_title, col_actor = st.columns([3, 2])
        with col_title:
            st.markdown(f"**{method['label']}**")
            st.caption(method["description"])
        with col_actor:
            st.caption(f"`{method['actor']}`")

        if configs:
            for cfg in configs:
                c1, c2, c3, c4 = st.columns([5, 2, 1, 1])
                with c1:
                    style = "opacity:0.4;text-decoration:line-through;" if not cfg["active"] else ""
                    st.markdown(f"<span style='{style}'><code>{cfg['value']}</code></span>",
                                unsafe_allow_html=True)
                with c2:
                    st.caption(SOURCE_BADGE.get(cfg.get("source", "manual"), "🖊️"))
                with c3:
                    icon = "✓" if cfg["active"] else "○"
                    if st.button(icon, key=f"tog_{cfg['id']}", help="Ativar/desativar"):
                        toggle_search_config(conn, cfg["id"], not cfg["active"])
                        st.rerun()
                with c4:
                    if st.button("✕", key=f"del_{cfg['id']}", help="Remover"):
                        delete_search_config(conn, cfg["id"])
                        st.rerun()
            st.caption(f"{active_count}/{len(configs)} ativas")
        else:
            st.info(f"Nenhuma seed configurada para este método.")

        with st.form(key=f"add_{platform}_{search_type}"):
            new_val = st.text_input(f"Adicionar {method['label']}",
                                    placeholder=method["placeholder"], label_visibility="collapsed")
            if st.form_submit_button(f"＋ Adicionar {method['label']}"):
                if new_val.strip():
                    upsert_search_config(conn, platform, search_type, new_val.strip(), source="manual")
                    st.rerun()
                else:
                    st.warning("Valor não pode ser vazio.")

        st.divider()
