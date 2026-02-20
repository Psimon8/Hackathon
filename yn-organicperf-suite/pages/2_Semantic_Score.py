"""
Semantic Score — Streamlit page.
Analyses sémantiques des Top 10 SERP vs votre domaine (BERT + n-grams).
"""
import streamlit as st
import pandas as pd

from core.credentials import render_credentials_sidebar
from config.settings import COUNTRIES, LANGUAGES, DEFAULT_BERT_THRESHOLD, DEFAULT_LEVENSHTEIN_THRESHOLD
from modules.semantic_score.engine import SemanticScoreEngine
from export.excel_exporter import export_to_excel, default_filename

st.set_page_config(page_title="Semantic Score", page_icon="📊", layout="wide")
render_credentials_sidebar()

# ── Header ──────────────────────────────────────────────────────────────────
st.title("📊 Semantic Score")
st.markdown("Analyse sémantique des Top 10 vs votre domaine — scoring BERT + n-grams pondérés SEO.")

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Paramètres Semantic Score")
    keywords_raw = st.text_area(
        "Mots-clés (un par ligne)",
        placeholder="seo paris\nagence seo lyon",
        height=120,
    )
    domain = st.text_input("Votre domaine", placeholder="example.com")

    # Country → use short code expected by SemanticScoreEngine (COUNTRY_CODES)
    country_names = list(COUNTRIES.keys())
    country_sel = st.selectbox("Pays", country_names, index=country_names.index("France"), key="sem_country")

    lang_names = list(LANGUAGES.keys())
    language_sel = st.selectbox("Langue", lang_names, index=lang_names.index("French"), key="sem_lang")

    with st.expander("⚙️ Paramètres avancés"):
        num_urls = st.slider("Nombre d'URLs à analyser", 3, 20, 10)
        bert_thresh = st.slider("Seuil BERT", 0.0, 1.0, DEFAULT_BERT_THRESHOLD, 0.01)
        lev_thresh = st.slider("Seuil Levenshtein", 0.0, 1.0, DEFAULT_LEVENSHTEIN_THRESHOLD, 0.01)
        use_onpage = st.checkbox("Utiliser OnPage API (fallback)", value=True)

    run_btn = st.button("🚀 Lancer l'analyse", type="primary", use_container_width=True)

# ── Map country name → short code ──────────────────────────────────────────
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

    lang_code = LANGUAGES[language_sel]
    country_short = _COUNTRY_SHORT.get(country_sel, "FR")

    engine = SemanticScoreEngine(language=lang_code)

    progress = st.progress(0, text="Démarrage…")
    status = st.empty()

    def on_progress(cur: int, total: int, kw: str):
        progress.progress(cur / total, text=f"Keyword {cur}/{total}")
        status.caption(f"Analyse sémantique : **{kw}**")

    with st.spinner("Analyse sémantique en cours…"):
        results = engine.analyze_keywords(
            keywords=keywords,
            domain=domain,
            country=country_short,
            language=lang_code,
            num_urls=num_urls,
            bert_threshold=bert_thresh,
            lev_threshold=lev_thresh,
            use_onpage=use_onpage,
            on_progress=on_progress,
        )

    progress.empty()
    status.empty()
    st.session_state["semantic_results"] = results
    st.success(f"✅ Analyse terminée — {len(results)} mots-clés traités")

# ── Display ─────────────────────────────────────────────────────────────────
if "semantic_results" in st.session_state:
    results = st.session_state["semantic_results"]

    # Master table
    rows = []
    for r in results:
        rows.append({
            "Keyword": r.keyword,
            "Score moyen": round(r.average_score, 2) if r.average_score else 0,
            "Score concurrent": round(r.average_competitor_score, 2) if r.average_competitor_score else 0,
            "Score domaine": round(r.domain_score, 2) if r.domain_score else None,
            "Position domaine": r.domain_position,
            "Densité (%)": round(r.keyword_density, 3) if r.keyword_density else None,
            "Temps (s)": round(r.analysis_time, 1),
            "Erreur": r.error or "",
        })

    df_master = pd.DataFrame(rows)
    st.subheader("Résultats par mot-clé")
    st.dataframe(df_master, use_container_width=True, height=400)

    # Per-keyword details
    if len(results) > 0:
        st.divider()
        kw_sel = st.selectbox("Détail par mot-clé", [r.keyword for r in results])
        sel = next((r for r in results if r.keyword == kw_sel), None)

        if sel and sel.top_results:
            st.subheader(f"Top URLs — {sel.keyword}")
            url_rows = []
            for u in sel.top_results:
                url_rows.append({
                    "Position": u.position,
                    "URL": u.url,
                    "Titre": u.title or "",
                    "Score": round(u.semantic_score, 2) if u.semantic_score else "",
                    "Mots": u.word_count,
                    "Méthode": u.scrape_method or "",
                })
            st.dataframe(pd.DataFrame(url_rows), use_container_width=True)

        # N-gram differential
        if sel and sel.ngram_differential:
            st.subheader("Différentiel N-grams")
            for ng_type, diffs in sel.ngram_differential.items():
                if diffs:
                    st.caption(ng_type)
                    diff_df = pd.DataFrame([
                        {"N-gram": k, "Différence": v}
                        for k, v in sorted(diffs.items(), key=lambda x: x[1], reverse=True)[:20]
                    ])
                    st.dataframe(diff_df, use_container_width=True, height=250)

    # ── Export ──────────────────────────────────────────────────────────
    st.divider()
    xlsx_bytes = export_to_excel(semantic_results=results)
    st.download_button(
        label="📥 Télécharger XLSX",
        data=xlsx_bytes,
        file_name=default_filename("semantic_score"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
