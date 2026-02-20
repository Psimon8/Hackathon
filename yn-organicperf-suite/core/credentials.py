"""
Credentials management for yn-organicperf-suite.
Loads from .env file by default, with Streamlit session_state override support.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()


@dataclass
class Credentials:
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    openai_api_key: str = ""


def get_credentials() -> Credentials:
    """
    Get API credentials. Priority:
    1. Streamlit session_state overrides (if available)
    2. Environment variables / .env file
    """
    creds = Credentials(
        dataforseo_login=os.getenv("DATAFORSEO_LOGIN", ""),
        dataforseo_password=os.getenv("DATAFORSEO_PASSWORD", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    )

    # Try Streamlit session_state override
    try:
        import streamlit as st
        if "credentials_override" in st.session_state:
            override = st.session_state["credentials_override"]
            if override.get("dataforseo_login"):
                creds.dataforseo_login = override["dataforseo_login"]
            if override.get("dataforseo_password"):
                creds.dataforseo_password = override["dataforseo_password"]
            if override.get("openai_api_key"):
                creds.openai_api_key = override["openai_api_key"]
    except ImportError:
        pass

    return creds


def render_credentials_sidebar():
    """Render credentials override fields in Streamlit sidebar."""
    import streamlit as st

    with st.sidebar.expander("🔑 API Credentials", expanded=False):
        st.caption("Laissez vide pour utiliser le fichier .env")

        current = st.session_state.get("credentials_override", {})

        dfs_login = st.text_input(
            "DataForSEO Login",
            value=current.get("dataforseo_login", ""),
            key="cred_dfs_login",
        )
        dfs_password = st.text_input(
            "DataForSEO Password",
            value=current.get("dataforseo_password", ""),
            type="password",
            key="cred_dfs_password",
        )
        openai_key = st.text_input(
            "OpenAI API Key",
            value=current.get("openai_api_key", ""),
            type="password",
            key="cred_openai_key",
        )

        if st.button("💾 Sauvegarder", key="cred_save"):
            st.session_state["credentials_override"] = {
                "dataforseo_login": dfs_login,
                "dataforseo_password": dfs_password,
                "openai_api_key": openai_key,
            }
            st.success("Credentials mises à jour pour cette session")
