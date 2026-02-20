"""
EEAT Enhancer — Streamlit page.
Évaluation EEAT complète + recommandations personnalisées via GPT-4o-mini.
"""
import streamlit as st
import pandas as pd

from core.credentials import render_credentials_sidebar
from modules.content_scoring.engine import ContentScoringEngine
from export.excel_exporter import export_to_excel, default_filename

st.set_page_config(page_title="EEAT Enhancer", page_icon="🧠", layout="wide")
render_credentials_sidebar()

from core.theme import inject_theme
inject_theme()

# ── Header ──────────────────────────────────────────────────────────────────
st.title("🧠 EEAT Enhancer")
st.markdown("Évaluation E-E-A-T complète + recommandations personnalisées pour améliorer vos contenus.")

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Paramètres EEAT")
    urls_raw = st.text_area(
        "URLs à analyser (une par ligne)",
        placeholder="https://example.com/article-1\nhttps://example.com/article-2",
        height=180,
    )
    forced_lang = st.selectbox(
        "Forcer la langue d'analyse",
        ["Auto-detect", "French", "English", "Spanish", "German", "Portuguese", "Italian"],
        index=0,
    )
    run_btn = st.button("🚀 Lancer l'évaluation", type="primary", width='stretch')

_LANG_MAP = {
    "Auto-detect": None, "French": "fr", "English": "en",
    "Spanish": "es", "German": "de", "Portuguese": "pt", "Italian": "it",
}

# ── Execution ───────────────────────────────────────────────────────────────
if run_btn:
    urls = [u.strip() for u in urls_raw.strip().splitlines() if u.strip()]
    if not urls:
        st.warning("Veuillez saisir au moins une URL.")
        st.stop()

    engine = ContentScoringEngine(forced_language=_LANG_MAP.get(forced_lang))

    progress = st.progress(0, text="Démarrage…")
    status = st.empty()

    def on_progress(cur: int, total: int, url: str):
        progress.progress(cur / total, text=f"URL {cur}/{total}")
        status.caption(f"Analyse : **{url[:80]}**")

    with st.spinner("Évaluation E-E-A-T en cours…"):
        results = engine.analyze_urls(urls, on_progress=on_progress)

    progress.empty()
    status.empty()
    st.session_state["eeat_results"] = results
    ok = sum(1 for r in results if r.status == "success")
    st.success(f"✅ Évaluation terminée — {ok}/{len(results)} pages analysées avec succès")

# ── Display ─────────────────────────────────────────────────────────────────
if "eeat_results" in st.session_state:
    results = st.session_state["eeat_results"]

    tab1, tab2, tab3 = st.tabs(["📊 Scores", "🔎 Détails", "💡 Suggestions"])

    with tab1:
        rows = []
        for r in results:
            comp = r.eeat_components or {}
            rows.append({
                "URL": r.url,
                "EEAT Global": r.eeat_global,
                "Expertise": comp.get("expertise", ""),
                "Experience": comp.get("experience", ""),
                "Authority": comp.get("authoritativeness", ""),
                "Trust": comp.get("trustworthiness", ""),
                "Composite": r.composite_score,
                "Compliance": r.compliance_score,
                "Qualité": r.quality_level,
                "Statut": r.status,
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, width='stretch', height=400)

        # Score distribution chart
        if any(r.eeat_global > 0 for r in results):
            chart_data = pd.DataFrame({
                "URL": [r.url[:50] for r in results if r.eeat_global > 0],
                "EEAT Global": [r.eeat_global for r in results if r.eeat_global > 0],
            }).set_index("URL")
            st.bar_chart(chart_data)

    with tab2:
        for r in results:
            with st.expander(f"{'✅' if r.status == 'success' else '❌'} {r.url[:80]}", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("EEAT Global", r.eeat_global)
                    st.metric("Composite", r.composite_score)
                with col2:
                    st.metric("Lisibilité", f"{r.lisibilite_score} ({r.lisibilite_label})")
                    st.metric("Mots", r.word_count)
                with col3:
                    st.metric("Sentiment", r.sentiment)
                    st.metric("Entité principale", r.main_entity or "—")

                if r.eeat_breakdown:
                    st.caption("Détail des sous-scores E-E-A-T")
                    bd = r.eeat_breakdown
                    bd_data = {
                        "Info originale": bd.info_originale,
                        "Description complète": bd.description_complete,
                        "Analyse pertinente": bd.analyse_pertinente,
                        "Valeur originale": bd.valeur_originale,
                        "Titre descriptif": bd.titre_descriptif,
                        "Titre sobre": bd.titre_sobre,
                        "Crédibilité": bd.credibilite,
                        "Qualité production": bd.qualite_production,
                        "Attention lecteur": bd.attention_lecteur,
                    }
                    st.bar_chart(pd.DataFrame(bd_data, index=["Score"]).T)

                if r.categorie:
                    st.caption(f"**Catégorie** : {r.categorie}")
                if r.resume:
                    st.caption(f"**Résumé** : {r.resume}")
                if r.title_suggested:
                    st.caption(f"**Titre suggéré** : {r.title_suggested}")
                if r.error:
                    st.error(r.error)

    with tab3:
        _PRIO_EMOJI = {"critical": "🔴", "major": "🟠", "minor": "🟡"}
        _AREA_BADGE = {
            "Expertise": "🎓", "Experience": "🧪", "Authoritativeness": "🏛️",
            "Trustworthiness": "🛡️", "Content Coverage": "📄",
        }
        _SECTION_LABEL = {
            "introduction": "Intro", "body": "Corps", "conclusion": "Conclusion",
            "title": "Titre", "overall": "Global",
        }
        for r in results:
            if not r.suggestions and not r.suggestions_detailed:
                continue
            with st.expander(f"{'✅' if r.status == 'success' else '❌'} {r.url[:80]}", expanded=True):
                if r.main_entity:
                    st.caption(f"Entité principale : **{r.main_entity}** — EEAT Global : **{r.eeat_global}/100**")
                if r.suggestions_detailed:
                    for rec in r.suggestions_detailed:
                        prio = rec.get("priority", "minor")
                        emoji = _PRIO_EMOJI.get(prio, "🟡")
                        area = rec.get("eeat_area", "")
                        area_badge = _AREA_BADGE.get(area, "📌")
                        section = _SECTION_LABEL.get(rec.get("section", "overall"), rec.get("section", ""))
                        recommendation = rec.get("recommendation", "")
                        rationale = rec.get("rationale", "")

                        st.markdown(
                            f"{emoji} **{recommendation}**\n\n"
                            f"&nbsp;&nbsp;&nbsp;&nbsp;{area_badge} `{area}` · 📍 `{section}`"
                        )
                        if rationale:
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;_💡 {rationale}_")
                        st.markdown("---")
                else:
                    # Fallback: template-based suggestions
                    for s in r.suggestions:
                        st.markdown(f"- {s}")
            st.divider()

    # ── Export ──────────────────────────────────────────────────────────
    st.divider()
    xlsx_bytes = export_to_excel(eeat_results=results)
    st.download_button(
        label="📥 Télécharger XLSX",
        data=xlsx_bytes,
        file_name=default_filename("eeat_scoring"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
