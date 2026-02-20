"""
Travel Agent Engine — keyword volume lookup via DataForSEO.
Supports direct keyword lists and keyword + Google Suggest expansion.
Optionally accepts date_from / date_to for monthly search filtering.
"""
import logging
from typing import Callable, List, Optional, Set

from core.dataforseo_client import DataForSEOClient
from core.google_suggest import GoogleSuggestClient
from core.models import KeywordVolumeResult

logger = logging.getLogger(__name__)


class TravelAgentEngine:
    """Keyword volume research via DataForSEO (with optional Google Suggest expansion)."""

    def __init__(self):
        self.client = DataForSEOClient()
        self.suggest_client = GoogleSuggestClient()

    # ═══════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════

    def research_custom(
        self,
        keywords: List[str],
        language: str = "fr",
        location_code: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> List[KeywordVolumeResult]:
        """Fetch volumes for a keyword list. All results have origin='direct'."""
        if not keywords:
            return []
        if on_progress:
            on_progress(f"Envoi de {len(keywords)} mots-clés à DataForSEO…")

        all_results: List[KeywordVolumeResult] = []
        batch_size = 1000
        for i in range(0, len(keywords), batch_size):
            batch = keywords[i : i + batch_size]
            results = self._fetch_batch(batch, language, location_code, date_from, date_to, on_progress)
            for r in results:
                r.origin = "direct"
            all_results.extend(results)

        all_results.sort(key=lambda r: r.search_volume or 0, reverse=True)
        return all_results

    def research_with_suggest(
        self,
        keywords: List[str],
        language: str = "fr",
        location_code: Optional[int] = None,
        country_short: str = "FR",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> List[KeywordVolumeResult]:
        """
        Fetch Google Suggest for each keyword, merge with originals,
        then fetch volumes for the combined (deduplicated) list.
        """
        if not keywords:
            return []

        # ── Step 1: Google Suggest ──────────────────────────────────────
        if on_progress:
            on_progress("🔍 Récupération des suggestions Google…")

        original_set: Set[str] = {kw.lower().strip() for kw in keywords}
        suggest_keywords: Set[str] = set()

        suggest_map = self.suggest_client.get_suggestions_batch(
            keywords=keywords,
            language=language,
            country=country_short,
            on_progress=lambda done, total, kw: (
                on_progress(f"Google Suggest : {done}/{total} — {kw}") if on_progress else None
            ),
        )
        for kw, suggestions in suggest_map.items():
            for s in suggestions:
                s_lower = s.lower().strip()
                if s_lower not in original_set:
                    suggest_keywords.add(s_lower)

        combined = list(keywords) + sorted(suggest_keywords)
        if on_progress:
            on_progress(
                f"✅ {len(suggest_keywords)} suggestions trouvées — "
                f"{len(combined)} mots-clés au total"
            )

        # ── Step 2: Fetch volumes ───────────────────────────────────────
        all_results: List[KeywordVolumeResult] = []
        batch_size = 1000
        for i in range(0, len(combined), batch_size):
            batch = combined[i : i + batch_size]
            results = self._fetch_batch(batch, language, location_code, date_from, date_to, on_progress)
            for r in results:
                r.origin = "direct" if r.keyword.lower().strip() in original_set else "suggest"
            all_results.extend(results)

        all_results.sort(key=lambda r: r.search_volume or 0, reverse=True)
        return all_results

    # ═══════════════════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════════════════

    def _fetch_batch(
        self,
        keywords: List[str],
        language: str,
        location_code: Optional[int],
        date_from: Optional[str],
        date_to: Optional[str],
        on_progress: Optional[Callable],
    ) -> List[KeywordVolumeResult]:
        task_id = self.client.post_keyword_volume_task(
            keywords=keywords,
            language_code=language,
            location_code=location_code,
            date_from=date_from,
            date_to=date_to,
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
