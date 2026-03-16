"""
Google OAuth authentication for Draper dashboard.
Restricts access to @worldpackers.com domain only.

Approach: uses st.query_params to capture the OAuth callback code,
since Streamlit does not expose custom HTTP routes.
The redirect URI points back to the same Streamlit URL — Google returns
?code=...&state=... as query params, which we read on the next render cycle.
"""
from __future__ import annotations

import os
from typing import Optional

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_oauth2_token
from google_auth_oauthlib.flow import Flow


def _client_id() -> str:
    v = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    if not v:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID not set")
    return v


def _client_secret() -> str:
    v = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    if not v:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_SECRET not set")
    return v


def _redirect_uri() -> str:
    """
    The redirect URI must match exactly what's registered in Google Cloud Console.
    Streamlit serves the app at root (/), so we redirect back to root with query params.
    Set OAUTH_REDIRECT_URI explicitly in Render environment variables to avoid mismatches.
    """
    explicit = os.getenv("OAUTH_REDIRECT_URI", "")
    if explicit:
        return explicit
    return "http://localhost:8501/"


def _is_worldpackers_email(email: str) -> bool:
    return email.lower().endswith("@worldpackers.com")


def _make_flow(state: Optional[str] = None) -> Flow:
    config = {
        "web": {
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_redirect_uri()],
        }
    }
    kwargs: dict = {"scopes": ["openid", "email", "profile"]}
    if state:
        kwargs["state"] = state
    return Flow.from_client_config(config, **kwargs)


def get_authenticated_user() -> Optional[dict]:
    return st.session_state.get("user_info")


def require_auth() -> dict:
    """
    Call this at the top of main(). Handles three cases:
      1. Already authenticated → return user_info
      2. OAuth callback arrived (query params have ?code=) → exchange for token
      3. Not authenticated → show login page and st.stop()
    """
    # Case 1: already logged in
    user = get_authenticated_user()
    if user:
        return user

    params = st.query_params

    # Case 2: Google redirected back with ?code=...
    if "code" in params:
        code = params["code"]
        state = params.get("state", "")
        saved_state = st.session_state.get("oauth_state", "")

        # Clear query params immediately to avoid re-processing on rerun
        st.query_params.clear()

        if state != saved_state:
            st.error("❌ Estado OAuth inválido. Tente novamente.")
            st.stop()

        try:
            flow = _make_flow(state=state)
            flow.redirect_uri = _redirect_uri()
            # Build full callback URL that google_auth_oauthlib expects
            callback_url = f"{_redirect_uri()}?code={code}&state={state}"
            flow.fetch_token(authorization_response=callback_url)

            id_token_str = flow.credentials.id_token
            user_info = verify_oauth2_token(id_token_str, Request(), _client_id())

            email = user_info.get("email", "")
            if not _is_worldpackers_email(email):
                st.error(f"❌ Acesso negado: {email} não é @worldpackers.com")
                st.stop()

            st.session_state.user_info = {
                "email": email,
                "name": user_info.get("name", email),
                "picture": user_info.get("picture", ""),
            }
            st.rerun()

        except Exception as exc:
            st.error(f"❌ Erro na autenticação: {exc}")
            st.stop()

    # Case 3: not logged in → show login page
    _show_login_page()
    st.stop()

    # unreachable, but satisfies type checker
    return {}


def _show_login_page() -> None:
    st.markdown(
        """
        <div style='text-align:center;padding:3rem 0 1rem 0'>
            <div style='font-size:3rem'>🔒</div>
            <h1 style='margin:0.5rem 0 0.25rem 0'>Acesso Restrito</h1>
            <p style='color:#6b7280;margin:0 0 2rem 0'>Este site é de uso interno.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔐 Login com Google", use_container_width=True, type="primary"):
            try:
                flow = _make_flow()
                flow.redirect_uri = _redirect_uri()
                auth_url, state = flow.authorization_url(
                    access_type="offline",
                    include_granted_scopes="true",
                    prompt="select_account",
                )
                st.session_state.oauth_state = state
                st.markdown(
                    f"<meta http-equiv='refresh' content='0; url={auth_url}'>",
                    unsafe_allow_html=True,
                )
                st.info("Redirecionando para o Google...")
            except RuntimeError as e:
                st.error(f"❌ {e}")
