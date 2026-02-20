"""
SERP Collector — Streamlit page.
Collects Google Organic, PAA, and Knowledge Graph results via DataForSEO.
"""
import streamlit as st
import pandas as pd
from dataclasses import asdict

from core.credentials import render_credentials_sidebar
from core.models import SERPResult
from config.settings import COUNTRIES, LANGUAGES
from modules.serp_collector.engine import collect_serp, analyze_domain_positions
from export.excel_exporter import export_to_excel, default_filename

st.set_page_config(page_title="SERP Collector", page_icon="🔍", layout="wide")
render_credentials_sidebar()

# ── Header ──────────────────────────────────────────────────────────────────
st.title("🔍 SERP Collector")
st.markdown("Collecte les résultats organiques, PAA et Knowledge Graph pour vos mots-clés.")

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Paramètres SERP")
    keywords_raw = st.text_area(
        "Mots-clés (un par ligne)",
        placeholder="seo paris\nagence seo\naudit seo",
        height=150,
    )
    country = st.selectbox("Pays", list(COUNTRIES.keys()), index=list(COUNTRIES.keys()).index("France"))
    language = st.selectbox("Langue", list(LANGUAGES.keys()), index=list(LANGUAGES.keys()).index("French"))
    depth = st.slider("Nombre de résultats", 3, 100, 10)
    run_btn = st.button("🚀 Lancer la collecte", type="primary", use_container_width=True)

# ── Execution ───────────────────────────────────────────────────────────────
if run_btn:
    keywords = [k.strip() for k in keywords_raw.strip().splitlines() if k.strip()]
    if not keywords:
        st.warning("Veuillez saisir au moins un mot-clé.")
        st.stop()

    country_code = COUNTRIES[country]
    language_code = LANGUAGES[language]

    progress = st.progress(0, text="Démarrage…")
    status = st.empty()

    def on_progress(cur: int, total: int, kw: str):
        progress.progress(cur / total, text=f"{cur}/{total} — {kw}")
        status.caption(f"Analyse : **{kw}**")

    with st.spinner("Collecte SERP en cours…"):
        organic_raw, paa_raw, kg_raw = collect_serp(
            keywords=keywords,
            country_code=country_code,
            language_code=language_code,
            depth=depth,
            on_progress=on_progress,
        )

    progress.empty()
    status.empty()
    st.success(f"✅ Collecte terminée — {len(organic_raw)} résultats organiques, {len(paa_raw)} PAA, {len(kg_raw)} KG")

    # ── Store in session state ──────────────────────────────────────────
    st.session_state["serp_organic"] = organic_raw
    st.session_state["serp_paa"] = paa_raw
    st.session_state["serp_kg"] = kg_raw

# ── Display results ─────────────────────────────────────────────────────────
if "serp_organic" in st.session_state:
    organic_raw = st.session_state["serp_organic"]
    paa_raw = st.session_state["serp_paa"]
    kg_raw = st.session_state["serp_kg"]

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Organic", "❓ PAA", "🧠 Knowledge Graph", "📈 Analyse domaines"])

    with tab1:
        if organic_raw:
            df = pd.DataFrame(organic_raw)
            cols_display = [c for c in ["keyword", "rank", "domain", "title", "url"] if c in df.columns]
            st.dataframe(df[cols_display] if cols_display else df, use_container_width=True, height=500)
        else:
            st.info("Aucun résultat organique.")

    with tab2:
        if paa_raw:
            df_paa = pd.DataFrame(paa_raw)
            st.dataframe(df_paa, use_container_width=True, height=400)
        else:
            st.info("Aucun résultat PAA.")

    with tab3:
        if kg_raw:
            df_kg = pd.DataFrame(kg_raw)
            st.dataframe(df_kg, use_container_width=True, height=400)
        else:
            st.info("Aucun Knowledge Graph.")

    with tab4:
        if organic_raw:
            domain_df = analyze_domain_positions(organic_raw)
            if not domain_df.empty:
                st.dataframe(domain_df, use_container_width=True, height=400)

                # Bar chart of top 20
                top20 = domain_df.head(20).set_index("domain")
                st.bar_chart(top20["Average Position"])
            else:
                st.info("Pas assez de données pour l'analyse.")

    # ── Export ──────────────────────────────────────────────────────────
    st.divider()
    serp_models = []
    for r in organic_raw:
        serp_models.append(SERPResult(
            keyword=r.get("keyword", ""),
            position=r.get("rank_absolute") or r.get("rank"),
            rank=r.get("rank"),
            domain=r.get("domain", ""),
            title=r.get("title", ""),
            url=r.get("url", ""),
            description=r.get("description", ""),
            result_type=r.get("type", "organic"),
        ))

    xlsx_bytes = export_to_excel(serp_results=serp_models)
    st.download_button(
        label="📥 Télécharger XLSX",
        data=xlsx_bytes,
        file_name=default_filename("serp_collector"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
