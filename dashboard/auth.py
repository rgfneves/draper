"""
Google OAuth authentication for Draper dashboard.
Restricts access to @worldpackers.com domain only.

Approach: manual OAuth2 flow via direct HTTP calls (no google_auth_oauthlib.Flow)
to avoid PKCE issues. Uses st.query_params to capture the callback code.
"""
from __future__ import annotations

import os
from urllib.parse import urlencode
from typing import Optional

import requests
import streamlit as st


_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_SCOPES = "openid email profile"


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
    explicit = os.getenv("OAUTH_REDIRECT_URI", "")
    if explicit:
        return explicit
    return "http://localhost:8501/"


def _is_worldpackers_email(email: str) -> bool:
    return email.lower().endswith("@worldpackers.com")


def _build_auth_url() -> str:
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


def _exchange_code_for_userinfo(code: str) -> dict:
    """Exchange authorization code for tokens, then fetch user info."""
    token_resp = requests.post(
        _GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": _redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    token_resp.raise_for_status()
    access_token = token_resp.json().get("access_token")

    userinfo_resp = requests.get(
        _GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    userinfo_resp.raise_for_status()
    return userinfo_resp.json()


def get_authenticated_user() -> Optional[dict]:
    return st.session_state.get("user_info")


def require_auth() -> dict:
    """
    Call this at the top of main(). Handles three cases:
      1. Already authenticated → return user_info
      2. OAuth callback arrived (?code=) → exchange for token and verify email
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
        st.query_params.clear()

        try:
            user_info = _exchange_code_for_userinfo(code)
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
                auth_url = _build_auth_url()
                st.markdown(
                    f"<meta http-equiv='refresh' content='0; url={auth_url}'>",
                    unsafe_allow_html=True,
                )
                st.info("Redirecionando para o Google...")
            except RuntimeError as e:
                st.error(f"❌ {e}")
