"""
Travel Agent — Streamlit page.
Recherche de volumes de mots-clés via DataForSEO, avec ou sans Google Suggest.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from core.credentials import render_credentials_sidebar
from config.settings import COUNTRIES, LANGUAGES
from modules.travel_agent.engine import TravelAgentEngine
from export.excel_exporter import export_to_excel, default_filename

st.set_page_config(page_title="Keyword Volumes", page_icon="📊", layout="wide")
render_credentials_sidebar()

from core.theme import inject_theme
inject_theme()

# ── Country short code map ──────────────────────────────────────────────────
_COUNTRY_SHORT = {
    "France": "FR", "United States": "US", "United Kingdom": "UK",
    "Germany": "DE", "Spain": "ES", "Italy": "IT", "Canada": "CA",
    "Australia": "AU", "Brazil": "BR", "Mexico": "MX",
    "Netherlands": "NL", "Belgium": "BE", "Switzerland": "CH",
    "Japan": "JP", "India": "IN", "Singapore": "SG",
}

# ── Header ──────────────────────────────────────────────────────────────────
st.title("📊 Keyword Volumes")
st.markdown(
    "Récupérez les volumes de recherche Google pour une liste de mots-clés, "
    "avec option d'expansion via **Google Suggest**."
)

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Paramètres")

    mode = st.radio(
        "Mode",
        ["Mots-clés seuls", "Mots-clés + Google Suggest"],
        index=0,
        help="Le mode Google Suggest récupère les suggestions d'autocomplétion pour chaque mot-clé.",
    )

    keywords_raw = st.text_area(
        "Mots-clés (un par ligne)",
        placeholder="hotel paris\nvol paris barcelone\nrestaurant lyon",
        height=150,
    )

    language_sel = st.selectbox(
        "Langue", list(LANGUAGES.keys()),
        index=list(LANGUAGES.keys()).index("French"),
        key="ta_lang",
    )
    country_sel = st.selectbox(
        "Pays (location)", list(COUNTRIES.keys()),
        index=list(COUNTRIES.keys()).index("France"),
        key="ta_country",
    )

    # ── Date range ──────────────────────────────────────────────────────
    st.subheader("Plage de dates")
    use_date_range = st.checkbox("Filtrer par période", value=False)
    date_from_val = None
    date_to_val = None
    if use_date_range:
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            date_from_val = st.date_input(
                "Du",
                value=date.today() - timedelta(days=365),
                max_value=date.today(),
            )
        with col_d2:
            date_to_val = st.date_input(
                "Au",
                value=date.today(),
                max_value=date.today(),
            )

    run_btn = st.button("🚀 Rechercher les volumes", type="primary", use_container_width=True)

# ── Execution ───────────────────────────────────────────────────────────────
if run_btn:
    kws = [k.strip() for k in keywords_raw.strip().splitlines() if k.strip()]
    if not kws:
        st.warning("Veuillez saisir au moins un mot-clé.")
        st.stop()

    lang_code = LANGUAGES[language_sel]
    location_code = COUNTRIES[country_sel]
    country_short = _COUNTRY_SHORT.get(country_sel, "FR")

    # Format dates
    df_str = date_from_val.strftime("%Y-%m-%d") if date_from_val else None
    dt_str = date_to_val.strftime("%Y-%m-%d") if date_to_val else None

    engine = TravelAgentEngine()
    log_area = st.empty()

    def on_progress(msg: str):
        log_area.info(msg)

    with st.spinner("Recherche de volumes en cours…"):
        if mode == "Mots-clés seuls":
            results = engine.research_custom(
                keywords=kws,
                language=lang_code,
                location_code=location_code,
                date_from=df_str,
                date_to=dt_str,
                on_progress=on_progress,
            )
        else:
            results = engine.research_with_suggest(
                keywords=kws,
                language=lang_code,
                location_code=location_code,
                country_short=country_short,
                date_from=df_str,
                date_to=dt_str,
                on_progress=on_progress,
            )

    log_area.empty()
    st.session_state["volume_results"] = results
    total_vol = sum(r.search_volume or 0 for r in results)
    n_direct = sum(1 for r in results if r.origin == "direct")
    n_suggest = sum(1 for r in results if r.origin == "suggest")
    summary = f"✅ {len(results)} mots-clés traités — Volume total : {total_vol:,}"
    if n_suggest:
        summary += f" — ({n_direct} directs, {n_suggest} suggestions)"
    st.success(summary)

# ── Display ─────────────────────────────────────────────────────────────────
if "volume_results" in st.session_state:
    results = st.session_state["volume_results"]

    tab1, tab2, tab3 = st.tabs(["📊 Tableau", "📅 Volumes mensuels", "🏆 Top 20"])

    # ── Tab 1: Table ────────────────────────────────────────────────────
    with tab1:
        rows = []
        for r in results:
            rows.append({
                "Keyword": r.keyword,
                "Volume": r.search_volume,
                "Competition": round(r.competition, 3) if r.competition else None,
                "CPC": round(r.cpc, 2) if r.cpc else None,
                "Origin": r.origin,
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Volume", ascending=False, na_position="last")
        st.dataframe(df, use_container_width=True, height=500)

    # ── Tab 2: Monthly volumes chart ────────────────────────────────────
    with tab2:
        st.subheader("Évolution mensuelle des volumes de recherche")

        # Build monthly data from all results
        monthly_rows = []
        for r in results:
            for m in r.monthly_searches:
                monthly_rows.append({
                    "Keyword": r.keyword,
                    "Year": m.get("year"),
                    "Month": m.get("month"),
                    "Volume": m.get("count") or 0,
                })

        if monthly_rows:
            df_monthly = pd.DataFrame(monthly_rows)
            df_monthly["Date"] = pd.to_datetime(
                df_monthly["Year"].astype(str) + "-" + df_monthly["Month"].astype(str).str.zfill(2) + "-01"
            )

            # ── Aggregated view ─────────────────────────────────────────
            st.markdown("#### Volume total agrégé par mois")
            agg = df_monthly.groupby("Date")["Volume"].sum().sort_index()
            st.bar_chart(agg, use_container_width=True)

            # ── Per-keyword view (top 10) ───────────────────────────────
            st.markdown("#### Saisonnalité — Top 10 mots-clés")
            top_kws = (
                df_monthly.groupby("Keyword")["Volume"]
                .sum()
                .nlargest(10)
                .index.tolist()
            )
            df_top = df_monthly[df_monthly["Keyword"].isin(top_kws)]
            if not df_top.empty:
                pivot = df_top.pivot_table(
                    index="Date", columns="Keyword", values="Volume", aggfunc="sum"
                ).fillna(0).sort_index()
                st.line_chart(pivot, use_container_width=True)
        else:
            st.info("Aucune donnée de volumes mensuels disponible.")

    # ── Tab 3: Top 20 ──────────────────────────────────────────────────
    with tab3:
        st.subheader("Top 20 mots-clés par volume")
        df_all = pd.DataFrame([{
            "Keyword": r.keyword,
            "Volume": r.search_volume or 0,
            "Origin": r.origin,
        } for r in results])

        if not df_all.empty:
            top20 = df_all.nlargest(20, "Volume")
            st.dataframe(top20, use_container_width=True)
            st.bar_chart(top20.set_index("Keyword")["Volume"], use_container_width=True)
        else:
            st.info("Aucune donnée de volume disponible.")

    # ── Export ──────────────────────────────────────────────────────────
    st.divider()
    xlsx_bytes = export_to_excel(volume_results=results)
    st.download_button(
        label="📥 Télécharger XLSX",
        data=xlsx_bytes,
        file_name=default_filename("keyword_volumes"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
