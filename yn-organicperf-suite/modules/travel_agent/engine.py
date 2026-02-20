"""
Travel Agent Engine — seeds + keyword volume lookup via DataForSEO.
Refactored from Travel Agent V3/api/dataforseo.py + main.py.
Uses shared DataForSEOClient from core/ for the 3-step keyword volume flow.
"""
import logging
from typing import Callable, Dict, List, Optional

from core.dataforseo_client import DataForSEOClient
from core.models import KeywordVolumeResult
from modules.travel_agent.seeds_loader import SeedsLoader

logger = logging.getLogger(__name__)


class TravelAgentEngine:
    """End-to-end keyword research: seeds → generate → search volumes."""

    def __init__(self):
        self.loader = SeedsLoader()
        self.client = DataForSEOClient()

    # ═══════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════

    def research(
        self,
        destinations: List[str],
        language: str = "fr",
        location_code: Optional[int] = None,
        categories: Optional[List[str]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> List[KeywordVolumeResult]:
        """
        Full pipeline: generate seeded keywords → fetch volumes via DataForSEO.
        Blocking (Streamlit-safe).
        """
        if on_progress:
            on_progress("Génération des mots-clés à partir des seeds…")

        kw_meta = self.loader.generate_keywords(language, destinations, categories)
        keywords = list(kw_meta.keys())

        if not keywords:
            logger.warning("No keywords generated — check seeds for lang=%s", language)
            return []

        if on_progress:
            on_progress(f"{len(keywords)} mots-clés générés — envoi à DataForSEO…")

        # Batch into chunks of 1000
        all_results: List[KeywordVolumeResult] = []
        batch_size = 1000
        for i in range(0, len(keywords), batch_size):
            batch = keywords[i : i + batch_size]
            results = self._fetch_batch(batch, language, location_code, on_progress)
            # Merge metadata
            for r in results:
                meta = kw_meta.get(r.keyword, {})
                r.destination = meta.get("destination", "")
                r.category = meta.get("category", "")
            all_results.extend(results)

        all_results.sort(key=lambda r: r.search_volume or 0, reverse=True)
        return all_results

    def research_custom(
        self,
        keywords: List[str],
        language: str = "fr",
        location_code: Optional[int] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> List[KeywordVolumeResult]:
        """Fetch volumes for an arbitrary keyword list (no seeds)."""
        if not keywords:
            return []
        if on_progress:
            on_progress(f"Envoi de {len(keywords)} mots-clés à DataForSEO…")
        return self._fetch_batch(keywords, language, location_code, on_progress)

    # ═══════════════════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════════════════

    def _fetch_batch(
        self,
        keywords: List[str],
        language: str,
        location_code: Optional[int],
        on_progress: Optional[Callable],
    ) -> List[KeywordVolumeResult]:
        task_id = self.client.post_keyword_volume_task(
            keywords=keywords,
            language_code=language,
            location_code=location_code,
        )
        if not task_id:
            logger.error("Failed to post keyword volume task")
            return []

        if on_progress:
            on_progress("Tâche soumise — attente des résultats DataForSEO…")

        ready = self.client.wait_for_task(task_id)
        if not ready:
            logger.error("Task %s timed out", task_id)
            return []

        raw = self.client.get_task_result(task_id)
        if not raw:
            return []

        results: List[KeywordVolumeResult] = []
        for item in raw:
            ms = item.get("monthly_searches") or []
            results.append(
                KeywordVolumeResult(
                    keyword=item.get("keyword", ""),
                    search_volume=item.get("search_volume"),
                    competition=item.get("competition"),
                    cpc=item.get("cpc"),
                    monthly_searches=[
                        {"year": m.get("year"), "month": m.get("month"), "count": m.get("search_volume")}
                        for m in ms
                    ],
                )
            )
        return results
