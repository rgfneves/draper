from __future__ import annotations

import streamlit as st

METHODS = {
    "instagram": [
        {
            "search_type": "hashtag",
            "label": "Hashtag",
            "actor": "apify/instagram-hashtag-scraper",
            "description": "Busca posts com essa hashtag e extrai os autores.",
            "placeholder": "ex: mochilero",
        },
        {
            "search_type": "location",
            "label": "Location ID",
            "actor": "apidojo/instagram-location-scraper",
            "description": "Busca posts marcados em um local via ID numérico do Instagram. Para encontrar o ID: abra instagram.com/explore/locations/{id}/ ou use a URL de um local no app. Ex: 213485029 = New York, 1445271 = São Paulo.",
            "placeholder": "ex: 213485029",
        },
    ],
    "tiktok": [
        {
            "search_type": "hashtag",
            "label": "Hashtag",
            "actor": "clockworks/tiktok-scraper",
            "description": "Busca vídeos com essa hashtag e extrai os criadores.",
            "placeholder": "ex: mochilero",
        },
        {
            "search_type": "keyword_search",
            "label": "Keyword Search",
            "actor": "clockworks/tiktok-user-search-scraper",
            "description": "Busca diretamente por perfis de usuários usando palavras-chave. Retorna criadores, não vídeos.",
            "placeholder": "ex: mochileiro brasil viagem",
        },
        {
            "search_type": "country_code",
            "label": "Country Filter",
            "actor": "apidojo/tiktok-scraper",
            "description": "Filtra criadores por país de origem. Use códigos ISO 2 letras. TikTok não tem location scraper dedicado — este filtro combina com as hashtags ativas.",
            "placeholder": "ex: US, GB, DE, FR, CA",
        },
    ],
}

SOURCE_BADGE = {
    "manual": ("🖊️ Manual", "blue"),
    "ai": ("🤖 AI", "violet"),
}

TAG_COLORS = ["green", "orange", "red", "violet", "blue", "gray"]


def _tag_color(tag: str) -> str:
    return TAG_COLORS[hash(tag) % len(TAG_COLORS)]


def render(conn) -> None:
    st.header("Search Seeds")
    st.caption(
        "Define o que o pipeline busca. Cada seed ativa gera chamadas ao Apify — "
        "controle a quantidade para controlar custos."
    )

    tab_ig, tab_tt = st.tabs(["Instagram", "TikTok"])
    for tab, platform in zip([tab_ig, tab_tt], ["instagram", "tiktok"]):
        with tab:
            _render_platform(conn, platform)


def _render_platform(conn, platform: str) -> None:
    from db.repository import (
        delete_search_config,
        get_search_configs,
        toggle_search_config,
        update_search_config_tags,
        upsert_search_config,
    )

    all_configs = get_search_configs(conn, platform=platform, active_only=False)

    for method in METHODS[platform]:
        search_type = method["search_type"]
        configs = [c for c in all_configs if c["search_type"] == search_type]
        active_count = sum(1 for c in configs if c["active"])

        st.subheader(method["label"])
        col_desc, col_actor = st.columns([3, 2])
        with col_desc:
            st.caption(method["description"])
        with col_actor:
            st.caption(f"Actor: `{method['actor']}`")

        if configs:
            for cfg in configs:
                editing_key = f"editing_tags_{cfg['id']}"

                col_value, col_tags, col_source, col_edit, col_toggle, col_del = st.columns([4, 3, 2, 1, 1, 1])

                with col_value:
                    style = "" if cfg["active"] else "color: #888; text-decoration: line-through;"
                    st.markdown(f"<span style='{style}'><code>{cfg['value']}</code></span>", unsafe_allow_html=True)

                with col_tags:
                    tags = cfg.get("tags", [])
                    if tags:
                        tag_html = " ".join(
                            f"<span style='background:#1f3a5f;color:#7eb8f7;border-radius:4px;padding:1px 6px;font-size:0.72rem;margin-right:2px'>{t}</span>"
                            for t in tags
                        )
                        st.markdown(tag_html, unsafe_allow_html=True)
                    else:
                        st.caption("—")

                with col_source:
                    badge_label, badge_color = SOURCE_BADGE.get(cfg.get("source", "manual"), ("🖊️ Manual", "blue"))
                    st.markdown(f":{badge_color}[{badge_label}]")

                with col_edit:
                    if st.button("🏷️", key=f"edit_tags_{cfg['id']}", help="Editar tags"):
                        st.session_state[editing_key] = not st.session_state.get(editing_key, False)
                        st.rerun()

                with col_toggle:
                    icon = "✓" if cfg["active"] else "○"
                    if st.button(icon, key=f"toggle_{cfg['id']}", help="Ativar/desativar"):
                        toggle_search_config(conn, cfg["id"], not cfg["active"])
                        st.rerun()

                with col_del:
                    if st.button("✕", key=f"del_{cfg['id']}", help="Remover"):
                        delete_search_config(conn, cfg["id"])
                        st.rerun()

                # Inline tag editor
                if st.session_state.get(editing_key, False):
                    with st.container():
                        current_tags_str = ", ".join(cfg.get("tags", []))
                        with st.form(key=f"tags_form_{cfg['id']}"):
                            new_tags_input = st.text_input(
                                "Tags (separadas por vírgula)",
                                value=current_tags_str,
                                placeholder="ex: brasil, espanhol, budget",
                                help="Tags para organizar e filtrar seeds na hora de executar.",
                            )
                            c_save, c_cancel = st.columns(2)
                            save = c_save.form_submit_button("Salvar", use_container_width=True, type="primary")
                            cancel = c_cancel.form_submit_button("Cancelar", use_container_width=True)
                        if save:
                            new_tags = [t.strip() for t in new_tags_input.split(",") if t.strip()]
                            update_search_config_tags(conn, cfg["id"], new_tags)
                            st.session_state[editing_key] = False
                            st.rerun()
                        if cancel:
                            st.session_state[editing_key] = False
                            st.rerun()

            st.caption(f"{active_count} de {len(configs)} ativas")
        else:
            st.info(f"Nenhum {method['label'].lower()} configurado.")

        with st.form(key=f"add_{platform}_{search_type}"):
            fc1, fc2 = st.columns([3, 2])
            with fc1:
                new_value = st.text_input(
                    f"Adicionar {method['label']}",
                    placeholder=method["placeholder"],
                )
            with fc2:
                new_tags_input = st.text_input(
                    "Tags (opcional, separadas por vírgula)",
                    placeholder="ex: brasil, budget",
                )
            if st.form_submit_button("Adicionar"):
                if new_value.strip():
                    new_tags = [t.strip() for t in new_tags_input.split(",") if t.strip()]
                    upsert_search_config(conn, platform, search_type, new_value.strip(), source="manual", tags=new_tags)
                    st.rerun()
                else:
                    st.warning("O valor não pode ser vazio.")

        st.divider()
