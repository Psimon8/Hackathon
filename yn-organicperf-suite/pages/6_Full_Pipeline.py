"""
Full Pipeline — Streamlit page.
Enchaîne les 5 modules : SERP → Semantic Score → EEAT → Fan-out → Volumes.
"""
import streamlit as st
import pandas as pd

from core.credentials import render_credentials_sidebar
from config.settings import COUNTRIES, LANGUAGES
from core.models import SERPResult
from modules.serp_collector.engine import collect_serp, analyze_domain_positions
from modules.semantic_score.engine import SemanticScoreEngine
from modules.content_scoring.engine import ContentScoringEngine
from modules.fanout.generator import FanoutGenerator
from modules.travel_agent.engine import TravelAgentEngine
from export.excel_exporter import export_to_excel, default_filename

st.set_page_config(page_title="Full Pipeline", page_icon="🚀", layout="wide")
render_credentials_sidebar()

# ── Header ──────────────────────────────────────────────────────────────────
st.title("🚀 Pipeline complet")
st.markdown("""
Enchaîne automatiquement les 5 étapes :
1. **SERP Collector** — Collecte Top N
2. **Semantic Score** — Analyse sémantique vs votre domaine
3. **Content Scoring** — Évaluation E-E-A-T des Top URLs
4. **Fan-out** — Expansion sémantique des mots-clés
5. **Travel Agent** — Volumes de recherche des queries fan-out
""")

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Paramètres Pipeline")
    keywords_raw = st.text_area(
        "Mots-clés (un par ligne)",
        placeholder="seo paris\nagence seo lyon",
        height=120,
        key="pipe_kw",
    )
    domain = st.text_input("Votre domaine", placeholder="example.com", key="pipe_domain")

    country_names = list(COUNTRIES.keys())
    country_sel = st.selectbox("Pays", country_names, index=country_names.index("France"), key="pipe_country")
    lang_names = list(LANGUAGES.keys())
    language_sel = st.selectbox("Langue", lang_names, index=lang_names.index("French"), key="pipe_lang")

    depth = st.slider("Profondeur SERP", 3, 20, 10, key="pipe_depth")
    eeat_top_n = st.slider("URLs à scorer (EEAT)", 1, 10, 3, key="pipe_eeat_n")
    fanout_lang = st.selectbox("Langue fan-out", ["fr", "en", "es", "de", "pt"], index=0, key="pipe_fo_lang")

    # Steps to run
    steps = st.multiselect(
        "Étapes à exécuter",
        ["SERP", "Semantic Score", "Content Scoring", "Fan-out", "Volumes"],
        default=["SERP", "Semantic Score", "Content Scoring", "Fan-out", "Volumes"],
    )

    run_btn = st.button("🚀 Lancer le pipeline", type="primary", width='stretch')

# ── Country short map ───────────────────────────────────────────────────────
_COUNTRY_SHORT = {
    "France": "FR", "United States": "US", "United Kingdom": "UK",
    "Germany": "DE", "Spain": "ES", "Italy": "IT", "Canada": "CA",
    "Australia": "AU", "Brazil": "BR", "Mexico": "MX",
    "Netherlands": "NL", "Belgium": "BE", "Switzerland": "CH",
    "Japan": "JP", "India": "IN", "Singapore": "SG",
}

# ── Execution ───────────────────────────────────────────────────────────────
if run_btn:
    keywords = [k.strip() for k in keywords_raw.strip().splitlines() if k.strip()]
    if not keywords:
        st.warning("Veuillez saisir au moins un mot-clé.")
        st.stop()

    country_code = COUNTRIES[country_sel]
    lang_code = LANGUAGES[language_sel]
    country_short = _COUNTRY_SHORT.get(country_sel, "FR")

    pipeline_results = {}
    overall = st.progress(0, text="Pipeline…")
    step_status = st.empty()
    n_steps = len(steps)
    step_i = 0

    # ── 1. SERP ─────────────────────────────────────────────────────────
    if "SERP" in steps:
        step_i += 1
        overall.progress(step_i / n_steps, text=f"Étape {step_i}/{n_steps} — SERP Collector")
        step_status.info("🔍 Collecte SERP…")

        organic_raw, paa_raw, kg_raw = collect_serp(
            keywords=keywords,
            country_code=country_code,
            language_code=lang_code,
            depth=depth,
        )
        pipeline_results["serp_organic"] = organic_raw
        pipeline_results["serp_paa"] = paa_raw
        pipeline_results["serp_kg"] = kg_raw

        # Convert to SERPResult models
        serp_models = [
            SERPResult(
                keyword=r.get("keyword", ""),
                position=r.get("rank_absolute") or r.get("rank"),
                rank=r.get("rank"),
                domain=r.get("domain", ""),
                title=r.get("title", ""),
                url=r.get("url", ""),
                description=r.get("description", ""),
                result_type=r.get("type", "organic"),
            )
            for r in organic_raw
        ]
        pipeline_results["serp_models"] = serp_models
        step_status.success(f"✅ SERP : {len(organic_raw)} résultats")

    # ── 2. Semantic Score ────────────────────────────────────────────────
    if "Semantic Score" in steps:
        step_i += 1
        overall.progress(step_i / n_steps, text=f"Étape {step_i}/{n_steps} — Semantic Score")
        step_status.info("📊 Analyse sémantique…")

        engine = SemanticScoreEngine(language=lang_code)
        sem_results = engine.analyze_keywords(
            keywords=keywords,
            domain=domain,
            country=country_short,
            language=lang_code,
            num_urls=depth,
        )
        pipeline_results["semantic_results"] = sem_results
        step_status.success(f"✅ Semantic Score : {len(sem_results)} analyses")

    # ── 3. Content Scoring ───────────────────────────────────────────────
    if "Content Scoring" in steps:
        step_i += 1
        overall.progress(step_i / n_steps, text=f"Étape {step_i}/{n_steps} — Content Scoring")
        step_status.info("📝 Évaluation E-E-A-T…")

        # Collect top URLs from SERP or semantic results
        eeat_urls = []
        if "serp_organic" in pipeline_results:
            seen = set()
            for r in pipeline_results["serp_organic"]:
                url = r.get("url", "")
                if url and url not in seen:
                    eeat_urls.append(url)
                    seen.add(url)
                if len(eeat_urls) >= eeat_top_n:
                    break

        if eeat_urls:
            eeat_engine = ContentScoringEngine()
            eeat_results = eeat_engine.analyze_urls(eeat_urls)
            pipeline_results["eeat_results"] = eeat_results
            ok = sum(1 for r in eeat_results if r.status == "success")
            step_status.success(f"✅ EEAT : {ok}/{len(eeat_results)} pages")
        else:
            step_status.warning("⚠️ Pas d'URLs disponibles pour le scoring EEAT")

    # ── 4. Fan-out ───────────────────────────────────────────────────────
    if "Fan-out" in steps:
        step_i += 1
        overall.progress(step_i / n_steps, text=f"Étape {step_i}/{n_steps} — Fan-out")
        step_status.info("🌐 Génération du fan-out…")

        gen = FanoutGenerator()
        fo_results = gen.generate_batch(keywords, language=fanout_lang)
        pipeline_results["fanout_results"] = fo_results
        step_status.success(f"✅ Fan-out : {len(fo_results)} mots-clés traités")

    # ── 5. Volumes ───────────────────────────────────────────────────────
    if "Volumes" in steps:
        step_i += 1
        overall.progress(step_i / n_steps, text=f"Étape {step_i}/{n_steps} — Search Volumes")
        step_status.info("✈️ Recherche de volumes…")

        # Collect queries from fan-out
        volume_keywords = list(keywords)  # start with original
        if "fanout_results" in pipeline_results:
            for fr in pipeline_results["fanout_results"]:
                top_qs = FanoutGenerator.extract_top_queries(fr, top_n=10)
                volume_keywords.extend(top_qs)
        # Deduplicate
        volume_keywords = list(dict.fromkeys(volume_keywords))

        if volume_keywords:
            ta_engine = TravelAgentEngine()
            vol_results = ta_engine.research_custom(
                keywords=volume_keywords,
                language=lang_code,
                location_code=country_code,
            )
            pipeline_results["volume_results"] = vol_results
            step_status.success(f"✅ Volumes : {len(vol_results)} mots-clés")

    overall.progress(1.0, text="Pipeline terminé ✅")
    st.session_state["pipeline_results"] = pipeline_results
    st.balloons()

# ── Display ─────────────────────────────────────────────────────────────────
if "pipeline_results" in st.session_state:
    pr = st.session_state["pipeline_results"]

    tabs_names = []
    if "serp_models" in pr:
        tabs_names.append("SERP")
    if "semantic_results" in pr:
        tabs_names.append("Semantic Score")
    if "eeat_results" in pr:
        tabs_names.append("EEAT")
    if "fanout_results" in pr:
        tabs_names.append("Fan-out")
    if "volume_results" in pr:
        tabs_names.append("Volumes")

    if not tabs_names:
        st.info("Aucun résultat à afficher.")
        st.stop()

    tabs = st.tabs(tabs_names)
    tab_idx = 0

    if "serp_models" in pr:
        with tabs[tab_idx]:
            df = pd.DataFrame([{
                "Keyword": r.keyword, "Position": r.position,
                "Domain": r.domain, "Title": r.title, "URL": r.url,
            } for r in pr["serp_models"]])
            st.dataframe(df, width='stretch', height=400)
        tab_idx += 1

    if "semantic_results" in pr:
        with tabs[tab_idx]:
            rows = [{
                "Keyword": r.keyword,
                "Avg Score": round(r.average_score, 2) if r.average_score else 0,
                "Domain Score": round(r.domain_score, 2) if r.domain_score else None,
                "Domain Pos": r.domain_position,
                "Error": r.error or "",
            } for r in pr["semantic_results"]]
            st.dataframe(pd.DataFrame(rows), width='stretch', height=400)
        tab_idx += 1

    if "eeat_results" in pr:
        with tabs[tab_idx]:
            rows = [{
                "URL": r.url, "EEAT Global": r.eeat_global,
                "Composite": r.composite_score, "Quality": r.quality_level,
                "Status": r.status,
            } for r in pr["eeat_results"]]
            st.dataframe(pd.DataFrame(rows), width='stretch', height=400)
        tab_idx += 1

    if "fanout_results" in pr:
        with tabs[tab_idx]:
            rows = [{
                "Keyword": r.keyword, "Topic": r.topic,
                "Mandatory": sum(len(f.queries) for f in r.mandatory),
                "Recommended": sum(len(f.queries) for f in r.recommended),
                "Optional": sum(len(f.queries) for f in r.optional),
            } for r in pr["fanout_results"]]
            st.dataframe(pd.DataFrame(rows), width='stretch', height=300)
        tab_idx += 1

    if "volume_results" in pr:
        with tabs[tab_idx]:
            rows = [{
                "Keyword": r.keyword,
                "Volume": r.search_volume,
                "CPC": r.cpc,
                "Competition": r.competition,
            } for r in pr["volume_results"]]
            df = pd.DataFrame(rows).sort_values("Volume", ascending=False, na_position="last")
            st.dataframe(df, width='stretch', height=400)
        tab_idx += 1

    # ── Unified export ──────────────────────────────────────────────────
    st.divider()
    xlsx_bytes = export_to_excel(
        serp_results=pr.get("serp_models"),
        semantic_results=pr.get("semantic_results"),
        eeat_results=pr.get("eeat_results"),
        fanout_results=pr.get("fanout_results"),
        volume_results=pr.get("volume_results"),
    )
    st.download_button(
        label="📥 Télécharger XLSX (toutes les données)",
        data=xlsx_bytes,
        file_name=default_filename("full_pipeline"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
