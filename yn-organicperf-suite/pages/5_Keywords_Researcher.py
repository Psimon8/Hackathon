"""
Keywords Researcher — Streamlit page.
Étude sémantique rapide : mots-clés → (Google Suggest) → déduplication → volumes DataForSEO → dataviz.
Fonctionne en 2 temps :
  Phase 1 : construction de la liste (mots-clés + suggest optionnel + dédup)
  Phase 2 : recherche de volumes + visualisation
"""
import streamlit as st
import pandas as pd
from datetime import date

from core.credentials import render_credentials_sidebar
from config.settings import COUNTRIES, LANGUAGES
from modules.keywords_researcher.engine import KeywordsResearcherEngine, deduplicate_keywords
from export.excel_exporter import export_to_excel, default_filename

st.set_page_config(page_title="Keywords Researcher", page_icon="🔍", layout="wide")
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
st.title("🔍 Keywords Researcher")
st.markdown(
    "Étude sémantique rapide à partir d'une liste de mots-clés. "
    "Expansion via **Google Suggest**, déduplication intelligente, "
    "puis recherche de **volumes de recherche** et data-visualisation."
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

    # ── Suggest settings (conditional) ──────────────────────────────────
    max_suggestions = 5
    if mode == "Mots-clés + Google Suggest":
        max_suggestions = st.slider(
            "Suggestions par mot-clé",
            min_value=1, max_value=9, value=5,
            help="Nombre maximum de suggestions Google Autocomplete retournées par mot-clé saisi.",
        )

    keywords_raw = st.text_area(
        "Mots-clés (un par ligne)",
        placeholder="hotel paris\nvol paris barcelone\nrestaurant lyon",
        height=150,
    )

    language_sel = st.selectbox(
        "Langue", list(LANGUAGES.keys()),
        index=list(LANGUAGES.keys()).index("French"),
        key="kr_lang",
    )
    country_sel = st.selectbox(
        "Pays (location)", list(COUNTRIES.keys()),
        index=list(COUNTRIES.keys()).index("France"),
        key="kr_country",
    )

    # ── Date range ──────────────────────────────────────────────────────
    st.subheader("Plage de dates")
    use_date_range = st.checkbox("Filtrer par période", value=True)
    date_from_val = None
    date_to_val = None
    if use_date_range:
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            date_from_val = st.date_input("Du", value=date(2025, 1, 1))
        with col_d2:
            date_to_val = st.date_input("Au", value=date(2026, 1, 1))

    # ── Advanced: dedup settings ────────────────────────────────────────
    with st.expander("⚙️ Déduplication avancée"):
        fuzzy_threshold = st.slider(
            "Seuil de similarité fuzzy",
            min_value=0.70, max_value=1.00, value=0.85, step=0.05,
            help="Deux mots-clés dont la similarité ≥ seuil seront considérés comme doublons. "
                 "1.0 = désactivé (exacte uniquement).",
        )

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1 — Construction de la liste de mots-clés
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    if mode == "Mots-clés + Google Suggest":
        explore_btn = st.button(
            "🔍 Explorer les suggestions",
            type="secondary",
            use_container_width=True,
            help="Récupère les suggestions Google puis affiche un tableau intermédiaire éditable.",
        )
    else:
        explore_btn = False

    run_btn = st.button("🚀 Rechercher les volumes", type="primary", use_container_width=True)


def _parse_keywords(raw: str) -> list[str]:
    return [k.strip() for k in raw.strip().splitlines() if k.strip()]


# ── Phase 1: Suggest exploration ────────────────────────────────────────────
if explore_btn:
    kws = _parse_keywords(keywords_raw)
    if not kws:
        st.warning("Veuillez saisir au moins un mot-clé.")
        st.stop()

    engine = KeywordsResearcherEngine()
    log_area = st.empty()
    country_short = _COUNTRY_SHORT.get(country_sel, "FR")
    lang_code = LANGUAGES[language_sel]

    with st.spinner("Récupération des suggestions Google…"):
        suggest_kws, combined = engine.get_suggestions(
            keywords=kws,
            language=lang_code,
            country_short=country_short,
            max_suggestions=max_suggestions,
            on_progress=lambda msg: log_area.info(msg),
        )
    log_area.empty()

    # Dedup
    deduped, n_exact, n_fuzzy = deduplicate_keywords(combined, fuzzy_threshold=fuzzy_threshold)

    # Build editable dataframe
    original_set = {k.lower().strip() for k in kws}
    rows = [{"Keyword": kw, "Origin": "direct" if kw.lower().strip() in original_set else "suggest", "Sélectionné": True} for kw in deduped]
    df_edit = pd.DataFrame(rows)

    # Store in session
    st.session_state["kr_suggest_df"] = df_edit
    st.session_state["kr_dedup_stats"] = (n_exact, n_fuzzy)
    st.session_state.pop("volume_results", None)  # clear old results

# ── Display Phase 1 results ────────────────────────────────────────────
if "kr_suggest_df" in st.session_state:
    st.subheader("📋 Phase 1 — Liste de mots-clés construite")
    n_exact, n_fuzzy = st.session_state.get("kr_dedup_stats", (0, 0))
    dedup_msg = f"🧹 **{n_exact + n_fuzzy}** doublons supprimés"
    if n_exact or n_fuzzy:
        dedup_msg += f" ({n_exact} exacts, {n_fuzzy} similaires)"
    st.markdown(dedup_msg)

    edited_df = st.data_editor(
        st.session_state["kr_suggest_df"],
        use_container_width=True,
        height=min(400, 35 * len(st.session_state["kr_suggest_df"]) + 40),
        column_config={
            "Keyword": st.column_config.TextColumn("Mot-clé", disabled=True),
            "Origin": st.column_config.TextColumn("Origine", disabled=True),
            "Sélectionné": st.column_config.CheckboxColumn("✅", default=True),
        },
        key="kr_editor",
    )
    st.session_state["kr_suggest_df"] = edited_df

    n_selected = edited_df["Sélectionné"].sum()
    n_direct = len(edited_df[edited_df["Origin"] == "direct"])
    n_suggest = len(edited_df[(edited_df["Origin"] == "suggest") & edited_df["Sélectionné"]])
    st.caption(f"{int(n_selected)} mots-clés sélectionnés ({n_direct} directs, {n_suggest} suggestions)")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2 — Recherche de volumes + Dataviz
# ═══════════════════════════════════════════════════════════════════════════

if run_btn:
    kws_raw = _parse_keywords(keywords_raw)
    if not kws_raw and "kr_suggest_df" not in st.session_state:
        st.warning("Veuillez saisir au moins un mot-clé.")
        st.stop()

    lang_code = LANGUAGES[language_sel]
    location_code = COUNTRIES[country_sel]
    country_short = _COUNTRY_SHORT.get(country_sel, "FR")

    # Determine final keyword list
    if "kr_suggest_df" in st.session_state:
        # Use edited suggest table
        sel_df = st.session_state["kr_suggest_df"]
        final_kws = sel_df[sel_df["Sélectionné"]]["Keyword"].tolist()
        original_set = set(sel_df[sel_df["Origin"] == "direct"]["Keyword"].str.lower().str.strip())
    elif mode == "Mots-clés + Google Suggest":
        # Suggest mode but user skipped Phase 1 — run suggest inline
        engine = KeywordsResearcherEngine()
        log_area = st.empty()
        with st.spinner("Récupération des suggestions Google…"):
            _, combined = engine.get_suggestions(
                keywords=kws_raw,
                language=lang_code,
                country_short=country_short,
                max_suggestions=max_suggestions,
                on_progress=lambda msg: log_area.info(msg),
            )
        log_area.empty()
        final_kws, n_exact, n_fuzzy = deduplicate_keywords(combined, fuzzy_threshold=fuzzy_threshold)
        if n_exact + n_fuzzy:
            st.info(f"🧹 {n_exact + n_fuzzy} doublons supprimés ({n_exact} exacts, {n_fuzzy} similaires)")
        original_set = {k.lower().strip() for k in kws_raw}
    else:
        # Keywords only — just dedup
        final_kws, n_exact, n_fuzzy = deduplicate_keywords(kws_raw, fuzzy_threshold=fuzzy_threshold)
        if n_exact + n_fuzzy:
            st.info(f"🧹 {n_exact + n_fuzzy} doublons supprimés ({n_exact} exacts, {n_fuzzy} similaires)")
        original_set = {k.lower().strip() for k in final_kws}

    if not final_kws:
        st.warning("Aucun mot-clé sélectionné.")
        st.stop()

    # Format dates
    df_str = date_from_val.strftime("%Y-%m-%d") if date_from_val else None
    dt_str = date_to_val.strftime("%Y-%m-%d") if date_to_val else None

    engine = KeywordsResearcherEngine()
    log_area = st.empty()

    with st.spinner(f"Recherche de volumes pour {len(final_kws)} mots-clés…"):
        results = engine.research_custom(
            keywords=final_kws,
            language=lang_code,
            location_code=location_code,
            date_from=df_str,
            date_to=dt_str,
            on_progress=lambda msg: log_area.info(msg),
        )
        # Tag origins
        for r in results:
            r.origin = "direct" if r.keyword.lower().strip() in original_set else "suggest"

    log_area.empty()
    st.session_state["volume_results"] = results

    total_vol = sum(r.search_volume or 0 for r in results)
    n_direct = sum(1 for r in results if r.origin == "direct")
    n_suggest = sum(1 for r in results if r.origin == "suggest")
    summary = f"✅ **{len(results)}** mots-clés traités — Volume total : **{total_vol:,}**"
    if n_suggest:
        summary += f" — ({n_direct} directs, {n_suggest} suggestions)"
    st.success(summary)

# ═══════════════════════════════════════════════════════════════════════════
# DISPLAY — Résultats & Dataviz
# ═══════════════════════════════════════════════════════════════════════════

if "volume_results" in st.session_state:
    results = st.session_state["volume_results"]

    # ═══════════ KPIs ═══════════════════════════════════════════════════
    st.subheader("📊 Phase 2 — Résultats")
    volumes = [r.search_volume or 0 for r in results]
    cpcs = [r.cpc for r in results if r.cpc]

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total mots-clés", f"{len(results):,}")
    kpi2.metric("Volume total", f"{sum(volumes):,}")
    kpi3.metric("Volume moyen", f"{int(sum(volumes) / max(len(volumes), 1)):,}")
    kpi4.metric("CPC moyen", f"{sum(cpcs) / max(len(cpcs), 1):.2f} €" if cpcs else "N/A")

    # ═══════════ Tabs ══════════════════════════════════════════════════
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Tableau complet",
        "📅 Tendances mensuelles",
        "🏆 Top Keywords",
        "📊 Distribution",
    ])

    # ── Tab 1: Full table with filters ──────────────────────────────────
    with tab1:
        rows = []
        for r in results:
            rows.append({
                "Keyword": r.keyword,
                "Volume": r.search_volume or 0,
                "Competition": round(r.competition, 3) if r.competition else None,
                "CPC (€)": round(r.cpc, 2) if r.cpc else None,
                "Origin": r.origin,
            })
        df = pd.DataFrame(rows)

        if not df.empty:
            # Filters
            fc1, fc2 = st.columns(2)
            with fc1:
                origin_filter = st.multiselect(
                    "Filtrer par origine", ["direct", "suggest"],
                    default=["direct", "suggest"],
                    key="kr_origin_filter",
                )
            with fc2:
                vol_range = st.slider(
                    "Plage de volume",
                    min_value=0,
                    max_value=int(df["Volume"].max()) if df["Volume"].max() > 0 else 100,
                    value=(0, int(df["Volume"].max()) if df["Volume"].max() > 0 else 100),
                    key="kr_vol_range",
                )

            mask = df["Origin"].isin(origin_filter) & df["Volume"].between(vol_range[0], vol_range[1])
            df_filtered = df[mask].sort_values("Volume", ascending=False)
            st.dataframe(df_filtered, use_container_width=True, height=500)
            st.caption(f"{len(df_filtered)} / {len(df)} mots-clés affichés")
        else:
            st.info("Aucune donnée.")

    # ── Tab 2: Monthly volumes chart ────────────────────────────────────
    with tab2:
        st.subheader("Évolution mensuelle des volumes de recherche")

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

            # Aggregated view
            st.markdown("#### Volume total agrégé par mois")
            agg = df_monthly.groupby("Date")["Volume"].sum().sort_index()
            st.bar_chart(agg, use_container_width=True)

            # Per-keyword: adjustable top N
            top_n = st.slider("Nombre de mots-clés dans le graphique", 5, 20, 10, key="kr_topn_monthly")
            st.markdown(f"#### Saisonnalité — Top {top_n} mots-clés")
            top_kws = (
                df_monthly.groupby("Keyword")["Volume"]
                .sum()
                .nlargest(top_n)
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

    # ── Tab 3: Top Keywords ─────────────────────────────────────────────
    with tab3:
        top_k = st.slider("Nombre de mots-clés", 10, 50, 20, key="kr_topk")
        st.subheader(f"Top {top_k} mots-clés par volume")

        df_all = pd.DataFrame([{
            "Keyword": r.keyword,
            "Volume": r.search_volume or 0,
            "CPC (€)": round(r.cpc, 2) if r.cpc else 0,
            "Origin": r.origin,
        } for r in results])

        if not df_all.empty:
            top_df = df_all.nlargest(top_k, "Volume")
            st.dataframe(top_df, use_container_width=True, hide_index=True)

            # Horizontal bar chart with color by origin
            chart_df = top_df.set_index("Keyword")[["Volume", "Origin"]].copy()
            chart_df = chart_df.sort_values("Volume", ascending=True)  # for horizontal look
            st.bar_chart(chart_df["Volume"], use_container_width=True, horizontal=True)
        else:
            st.info("Aucune donnée de volume disponible.")

    # ── Tab 4: Volume distribution ──────────────────────────────────────
    with tab4:
        st.subheader("Distribution des volumes de recherche")
        if results:
            vols = [r.search_volume or 0 for r in results]
            buckets = {"0": 0, "1–100": 0, "101–1K": 0, "1K–10K": 0, "10K+": 0}
            for v in vols:
                if v == 0:
                    buckets["0"] += 1
                elif v <= 100:
                    buckets["1–100"] += 1
                elif v <= 1000:
                    buckets["101–1K"] += 1
                elif v <= 10000:
                    buckets["1K–10K"] += 1
                else:
                    buckets["10K+"] += 1

            dist_df = pd.DataFrame({"Tranche": list(buckets.keys()), "Nombre de mots-clés": list(buckets.values())})
            st.bar_chart(dist_df.set_index("Tranche"), use_container_width=True)

            # Origin breakdown
            st.markdown("#### Répartition par origine")
            origin_counts = pd.DataFrame([{
                "Origin": r.origin,
                "Volume": r.search_volume or 0,
            } for r in results])
            if not origin_counts.empty:
                oc_agg = origin_counts.groupby("Origin").agg(
                    Mots_clés=("Origin", "count"),
                    Volume_total=("Volume", "sum"),
                    Volume_moyen=("Volume", "mean"),
                ).round(0)
                st.dataframe(oc_agg, use_container_width=True)
        else:
            st.info("Aucune donnée.")

    # ── Export ──────────────────────────────────────────────────────────
    st.divider()
    xlsx_bytes = export_to_excel(volume_results=results)
    st.download_button(
        label="📥 Télécharger XLSX",
        data=xlsx_bytes,
        file_name=default_filename("keywords_researcher"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
