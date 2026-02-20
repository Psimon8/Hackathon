"""
YN Organic-Perf Suite — Streamlit entry point.
Run with: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="YN Organic-Perf Suite",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

from core.theme import inject_theme  # noqa: E402
inject_theme()

from core.credentials import render_credentials_sidebar  # noqa: E402

# ── sidebar: credentials ────────────────────────────────────────────────────
render_credentials_sidebar()

# ── main page ──────────────────────────────────────────────────────────────
st.title("🔍 YN Organic-Perf Suite")
st.markdown("""
Bienvenue dans la suite d'outils SEO **YN Organic-Perf**.

Utilisez la **sidebar** pour naviguer entre les modules :

| # | Module | Description |
|---|--------|-------------|
| 1 | **SERP Collector** | Collecte les résultats organiques, PAA et Knowledge Graph via DataForSEO |
| 2 | **Semantic Score** | Analyse sémantique des Top 10 vs votre domaine (BERT + n-grams) |
| 3 | **Content Scoring** | Évaluation E-E-A-T complète de pages web via OpenAI |
| 4 | **Fan-out** | Expansion sémantique de mots-clés (Query Fan-Out) via OpenAI |
| 5 | **Keyword Volumes** | Volumes de recherche + Google Suggest via DataForSEO |
| 6 | **Pipeline complet** | Enchaîne tous les modules en séquence |

> Tous les résultats sont **exportables en XLSX** depuis chaque page.
""")

st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Modules", "5")
with col2:
    st.metric("Langues", "10+")
with col3:
    st.metric("Pays", "16")

st.info("💡 Configurez vos credentials API dans la sidebar avant de lancer les analyses.")
