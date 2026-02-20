"""
Travel Agent — Streamlit page.
Recherche de volumes de mots-clés par seeds + DataForSEO.
"""
import streamlit as st
import pandas as pd

from core.credentials import render_credentials_sidebar
from config.settings import COUNTRIES, LANGUAGES
from modules.travel_agent.engine import TravelAgentEngine
from modules.travel_agent.seeds_loader import SeedsLoader
from export.excel_exporter import export_to_excel, default_filename

st.set_page_config(page_title="Travel Agent", page_icon="✈️", layout="wide")
render_credentials_sidebar()

# ── Header ──────────────────────────────────────────────────────────────────
st.title("✈️ Travel Agent — Keyword Volumes")
st.markdown("Génère des mots-clés à partir de seeds et récupère les volumes de recherche via DataForSEO.")

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Paramètres Travel Agent")

    mode = st.radio("Mode", ["Seeds + Destinations", "Liste libre de mots-clés"], index=0)

    if mode == "Seeds + Destinations":
        destinations_raw = st.text_area(
            "Destinations (une par ligne)",
            placeholder="Paris\nBarcelone\nRome",
            height=120,
        )
        language_sel = st.selectbox("Langue des seeds", list(LANGUAGES.keys()), index=1, key="ta_lang")
        categories = st.multiselect(
            "Catégories",
            ["dreamer", "planner", "booker", "concierge"],
            default=["dreamer", "planner", "booker", "concierge"],
        )
    else:
        keywords_raw = st.text_area(
            "Mots-clés (un par ligne)",
            placeholder="hotel paris\nvol paris barcelone",
            height=150,
        )
        language_sel = st.selectbox("Langue", list(LANGUAGES.keys()), index=1, key="ta_lang_custom")

    country_sel = st.selectbox("Pays (location)", list(COUNTRIES.keys()), index=list(COUNTRIES.keys()).index("France"), key="ta_country")

    run_btn = st.button("🚀 Rechercher les volumes", type="primary", use_container_width=True)

# ── Execution ───────────────────────────────────────────────────────────────
if run_btn:
    lang_code = LANGUAGES[language_sel]
    location_code = COUNTRIES[country_sel]
    engine = TravelAgentEngine()

    log_area = st.empty()

    def on_progress(msg: str):
        log_area.info(msg)

    if mode == "Seeds + Destinations":
        dests = [d.strip() for d in destinations_raw.strip().splitlines() if d.strip()]
        if not dests:
            st.warning("Veuillez saisir au moins une destination.")
            st.stop()

        # Show generated keywords count
        loader = SeedsLoader()
        kw_meta = loader.generate_keywords(lang_code, dests, categories if categories else None)
        st.info(f"🔑 {len(kw_meta)} mots-clés générés à partir des seeds")

        with st.spinner("Recherche de volumes en cours…"):
            results = engine.research(
                destinations=dests,
                language=lang_code,
                location_code=location_code,
                categories=categories if categories else None,
                on_progress=on_progress,
            )
    else:
        kws = [k.strip() for k in keywords_raw.strip().splitlines() if k.strip()]
        if not kws:
            st.warning("Veuillez saisir au moins un mot-clé.")
            st.stop()
        with st.spinner("Recherche de volumes en cours…"):
            results = engine.research_custom(
                keywords=kws,
                language=lang_code,
                location_code=location_code,
                on_progress=on_progress,
            )

    log_area.empty()
    st.session_state["volume_results"] = results
    total_vol = sum(r.search_volume or 0 for r in results)
    st.success(f"✅ {len(results)} mots-clés traités — Volume total : {total_vol:,}")

# ── Display ─────────────────────────────────────────────────────────────────
if "volume_results" in st.session_state:
    results = st.session_state["volume_results"]

    tab1, tab2 = st.tabs(["📊 Tableau", "📈 Analyse"])

    with tab1:
        rows = []
        for r in results:
            rows.append({
                "Keyword": r.keyword,
                "Volume": r.search_volume,
                "Competition": round(r.competition, 3) if r.competition else None,
                "CPC": round(r.cpc, 2) if r.cpc else None,
                "Destination": r.destination,
                "Category": r.category,
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, height=500)

    with tab2:
        df = pd.DataFrame([{
            "Keyword": r.keyword,
            "Volume": r.search_volume or 0,
            "Destination": r.destination,
            "Category": r.category,
        } for r in results])

        if not df.empty and "Destination" in df.columns:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Volume par destination")
                dest_vol = df.groupby("Destination")["Volume"].sum().sort_values(ascending=False)
                if not dest_vol.empty:
                    st.bar_chart(dest_vol.head(20))

            with col2:
                st.subheader("Volume par catégorie")
                cat_vol = df.groupby("Category")["Volume"].sum().sort_values(ascending=False)
                if not cat_vol.empty:
                    st.bar_chart(cat_vol)

        st.subheader("Top 20 mots-clés")
        if not df.empty and "Volume" in df.columns:
            top20 = df.nlargest(20, "Volume")
            if not top20.empty:
                st.dataframe(top20, use_container_width=True)
        else:
            st.info("Aucune donnée de volume disponible.")

    # ── Export ──────────────────────────────────────────────────────────
    st.divider()
    xlsx_bytes = export_to_excel(volume_results=results)
    st.download_button(
        label="📥 Télécharger XLSX",
        data=xlsx_bytes,
        file_name=default_filename("travel_agent"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
