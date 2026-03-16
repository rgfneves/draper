"""
Draper Dashboard — entry point.

Usage:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from dashboard.auth import require_auth

st.set_page_config(
    page_title="Draper — Influencer Radar",
    page_icon="🎒",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def _get_connection():
    from db.connection import get_connection
    return get_connection()


# Process-ordered navigation
_NAV = [
    ("📊 Dashboard",   "overview"),
    ("🔍 Busca",       "seeds"),
    ("▶️ Executar",    "run"),
    ("🎯 Leads",       "leads"),
    ("👤 Perfis",      "profiles"),
]


def main() -> None:
    # Require authentication — handles login page, OAuth callback, and session
    user = require_auth()

    conn = _get_connection()

    # Hide Streamlit's auto-generated multipage nav (keep only our manual radio)
    st.markdown(
        "<style>[data-testid='stSidebarNav'] { display: none; }</style>",
        unsafe_allow_html=True,
    )

    # ── Sidebar brand ──────────────────────────────────────────────────────────
    st.sidebar.markdown(
        """
        <div style='padding:0.75rem 0 1.25rem 0'>
            <span style='font-size:1.5rem;font-weight:800;letter-spacing:-0.5px'>🎒 Draper</span><br>
            <span style='font-size:0.75rem;color:#9ca3af'>Influencer Radar Platform</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── User info and logout ───────────────────────────────────────────────────
    col_user, col_logout = st.sidebar.columns([3, 1])
    with col_user:
        st.caption(f"👤 {user.get('name', user.get('email', 'User'))}")
    with col_logout:
        if st.button("🚪", help="Logout", key="logout_btn"):
            st.session_state.clear()
            st.rerun()

    st.sidebar.markdown(
        "<p style='font-size:0.65rem;color:#6b7280;text-transform:uppercase;"
        "letter-spacing:1.2px;margin:0 0 6px 0'>Processo</p>",
        unsafe_allow_html=True,
    )

    page_label = st.sidebar.radio(
        "Processo",
        options=[name for name, _ in _NAV],
        label_visibility="collapsed",
    )

    # ── Apify usage footer (live from API, cached 5 min) ──────────────────────
    @st.cache_data(ttl=300)
    def _apify_usage():
        try:
            from platforms.apify_client import get_account_usage
            return get_account_usage()
        except Exception:
            return None

    usage = _apify_usage()
    st.sidebar.markdown("---")
    if usage:
        st.sidebar.markdown(
            f"<div style='font-size:0.65rem;color:#6b7280;margin-bottom:2px'>"
            f"Apify · {usage['cycle_start']} → {usage['cycle_end']}</div>"
            f"<div style='font-size:1.1rem;font-weight:700;color:#f59e0b'>"
            f"${usage['usage_usd']:.4f}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.caption("Apify: token não configurado")

    # ── Page routing ───────────────────────────────────────────────────────────
    module = dict(_NAV)[page_label]

    if module == "overview":
        from dashboard.pages.overview import render
    elif module == "seeds":
        from dashboard.pages.seeds import render
    elif module == "run":
        from dashboard.pages.run import render
    elif module == "leads":
        from dashboard.pages.leads import render
    else:
        from dashboard.pages.profiles import render

    render(conn)


if __name__ == "__main__":
    main()
