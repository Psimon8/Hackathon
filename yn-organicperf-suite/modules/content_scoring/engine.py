"""
Content Scoring Engine — orchestrates fetch → clean → lang → analyze → score.
Refactored from Scoring/content-analyzer pipeline.
"""
import logging
from typing import Callable, Dict, List, Optional

from core.models import EEATBreakdown, EEATResult
from core.openai_client import OpenAIClient
from modules.content_scoring.fetcher import ContentFetcher
from modules.content_scoring.cleaner import ContentCleaner
from modules.content_scoring.language import LanguageDetector
from modules.content_scoring.analyzer import ContentAnalyzer
from modules.content_scoring.scorer import ScoreCalculator

logger = logging.getLogger(__name__)


class ContentScoringEngine:
    """Full pipeline: URL list → EEAT results with improvements."""

    def __init__(
        self,
        openai_client: Optional[OpenAIClient] = None,
        prompt_path: Optional[str] = None,
        forced_language: Optional[str] = None,
    ):
        self.fetcher = ContentFetcher()
        self.cleaner = ContentCleaner()
        self.lang_detector = LanguageDetector()
        self.analyzer = ContentAnalyzer(openai_client=openai_client, prompt_path=prompt_path)
        self.scorer = ScoreCalculator()
        self.forced_language = forced_language

    # ═══════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════

    def analyze_urls(
        self,
        urls: List[str],
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[EEATResult]:
        """Analyse a list of URLs through the full pipeline. Blocking (Streamlit-safe)."""
        results: List[EEATResult] = []
        for idx, url in enumerate(urls, 1):
            if on_progress:
                on_progress(idx, len(urls), url)
            try:
                data = self._process_one(url)
                results.append(self._to_model(data))
            except Exception as e:
                logger.error("pipeline error %s: %s", url, e)
                results.append(EEATResult(url=url, status="error", error=str(e)))
        return results

    # ═══════════════════════════════════════════════════════════════════════
    # Pipeline per URL
    # ═══════════════════════════════════════════════════════════════════════

    def _process_one(self, url: str) -> Dict:
        # 1. Fetch
        data = self.fetcher.fetch_and_extract(url)
        if data["status"] == "error":
            return data

        # 2. Clean
        data = self.cleaner.clean(data)

        # 3. Language
        data = self.lang_detector.analyze(data, forced=self.forced_language)

        # 4. AI analysis (OpenAI)
        data = self.analyzer.analyze(data)

        # 5. Score calculation
        data = self.scorer.analyze_scores(data)
        return data

    @staticmethod
    def _to_model(data: Dict) -> EEATResult:
        bd = data.get("eeat_breakdown", {})
        breakdown = EEATBreakdown(
            info_originale=bd.get("info_originale", 0),
            description_complete=bd.get("description_complete", 0),
            analyse_pertinente=bd.get("analyse_pertinente", 0),
            valeur_originale=bd.get("valeur_originale", 0),
            titre_descriptif=bd.get("titre_descriptif", 0),
            titre_sobre=bd.get("titre_sobre", 0),
            credibilite=bd.get("credibilite", 0),
            qualite_production=bd.get("qualite_production", 0),
            attention_lecteur=bd.get("attention_lecteur", 0),
        )
        components = data.get("eeat_components", {})
        entity = data.get("entity_analysis", {})
        improvements = data.get("improvement_areas", [])
        suggestions = []
        for imp in improvements:
            for rec in imp.get("recommendations", []):
                suggestions.append(rec)

        return EEATResult(
            url=data.get("url", ""),
            title=data.get("title_cleaned", data.get("title", "")),
            title_suggested=data.get("title_suggested", ""),
            language=data.get("language_final", ""),
            eeat_global=data.get("eeat_global_calculated", data.get("eeat_global", 0)),
            eeat_breakdown=breakdown,
            eeat_components=components,
            main_entity=entity.get("main_entity", data.get("main_entity_ai", "")),
            entity_mentions=entity.get("entity_mentions_total", 0),
            sentiment=data.get("sentiment", "neutral"),
            lisibilite_score=data.get("lisibilite_score", 0),
            lisibilite_label=data.get("lisibilite_label", "moyen"),
            categorie=data.get("categorie", ""),
            resume=data.get("resume", ""),
            suggestions=suggestions,
            composite_score=data.get("composite_score", 0),
            compliance_score=data.get("compliance_score", 0),
            quality_level=data.get("eeat_quality_level", ""),
            word_count=data.get("content_words", 0),
            status=data.get("status", "success") if data.get("analysis_status") == "success" else data.get("analysis_status", "error"),
            error=data.get("error") or data.get("analysis_error"),
        )
