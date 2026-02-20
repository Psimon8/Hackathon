"""
Fan-out — Streamlit page.
Expansion sémantique de mots-clés via OpenAI (Query Fan-Out).
"""
import streamlit as st
import pandas as pd

from core.credentials import render_credentials_sidebar
from modules.fanout.generator import FanoutGenerator
from export.excel_exporter import export_to_excel, default_filename

st.set_page_config(page_title="Fan-out", page_icon="🌐", layout="wide")
render_credentials_sidebar()

from core.theme import inject_theme
inject_theme()

# ── Header ──────────────────────────────────────────────────────────────────
st.title("🌐 Query Fan-Out")
st.markdown("Expansion sémantique de vos mots-clés en facettes (mandatory / recommended / optional).")

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Paramètres Fan-out")
    keywords_raw = st.text_area(
        "Mots-clés (un par ligne)",
        placeholder="agence seo\ncréation site web",
        height=120,
    )
    language = st.selectbox(
        "Langue de génération",
        ["fr", "en", "es", "de", "pt"],
        index=0,
    )
    run_btn = st.button("🚀 Générer le fan-out", type="primary", width='stretch')

# ── Execution ───────────────────────────────────────────────────────────────
if run_btn:
    keywords = [k.strip() for k in keywords_raw.strip().splitlines() if k.strip()]
    if not keywords:
        st.warning("Veuillez saisir au moins un mot-clé.")
        st.stop()

    gen = FanoutGenerator()

    progress = st.progress(0, text="Démarrage…")
    status = st.empty()

    def on_progress(cur: int, total: int, kw: str):
        progress.progress(cur / total, text=f"Keyword {cur}/{total}")
        status.caption(f"Fan-out : **{kw}**")

    with st.spinner("Génération du fan-out en cours…"):
        results = gen.generate_batch(keywords, language=language, on_progress=on_progress)

    progress.empty()
    status.empty()
    st.session_state["fanout_results"] = results
    st.success(f"✅ Fan-out généré pour {len(results)} mots-clés")

# ── Display ─────────────────────────────────────────────────────────────────
if "fanout_results" in st.session_state:
    results = st.session_state["fanout_results"]

    for r in results:
        with st.expander(f"🔑 **{r.keyword}** → {r.topic}", expanded=True):
            if r.error:
                st.warning(f"⚠️ Erreur : {r.error}")

            if r.top_3_questions:
                st.subheader("Top 3 Questions")
                for i, q in enumerate(r.top_3_questions, 1):
                    st.markdown(f"{i}. {q}")

            st.subheader("Facettes")

            def _display_facets(facets, label, color):
                if not facets:
                    return
                st.markdown(f"**{label}** ({len(facets)} facettes)")
                for f in facets:
                    cols = st.columns([2, 1, 4])
                    with cols[0]:
                        st.markdown(f"**{f.facet}**")
                    with cols[1]:
                        st.caption(f"intent: {f.intent} | score: {f.importance_score}")
                    with cols[2]:
                        for q in f.queries:
                            st.markdown(f"- {q}")

            _display_facets(r.mandatory, "🔴 Mandatory", "red")
            _display_facets(r.recommended, "🟡 Recommended", "yellow")
            _display_facets(r.optional, "🟢 Optional", "green")

            if r.justification:
                st.caption(f"💬 {r.justification}")

            # Top queries extraction
            top_queries = FanoutGenerator.extract_top_queries(r, top_n=15)
            if top_queries:
                st.subheader("Top 15 Queries (classées)")
                for i, q in enumerate(top_queries, 1):
                    st.markdown(f"{i}. {q}")

    # ── Summary table ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Tableau récapitulatif")
    summary_rows = []
    for r in results:
        n_mand = sum(len(f.queries) for f in r.mandatory)
        n_rec = sum(len(f.queries) for f in r.recommended)
        n_opt = sum(len(f.queries) for f in r.optional)
        summary_rows.append({
            "Keyword": r.keyword,
            "Topic": r.topic,
            "Mandatory queries": n_mand,
            "Recommended queries": n_rec,
            "Optional queries": n_opt,
            "Total": n_mand + n_rec + n_opt,
        })
    st.dataframe(pd.DataFrame(summary_rows), width='stretch')

    # ── Export ──────────────────────────────────────────────────────────
    st.divider()
    xlsx_bytes = export_to_excel(fanout_results=results)
    st.download_button(
        label="📥 Télécharger XLSX",
        data=xlsx_bytes,
        file_name=default_filename("fanout"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
