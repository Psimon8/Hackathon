"""
Keywords Researcher Engine — keyword volume lookup via DataForSEO.
Supports direct keyword lists and keyword + Google Suggest expansion.
Optionally accepts date_from / date_to for monthly search filtering.
Includes fuzzy deduplication (Levenshtein) for cleaner keyword lists.
"""
import logging
from difflib import SequenceMatcher
from typing import Callable, Dict, List, Optional, Set, Tuple

from core.dataforseo_client import DataForSEOClient
from core.google_suggest import GoogleSuggestClient
from core.models import KeywordVolumeResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Deduplication utilities
# ═══════════════════════════════════════════════════════════════════════════

def deduplicate_keywords(
    keywords: List[str],
    fuzzy_threshold: float = 0.85,
) -> Tuple[List[str], int, int]:
    """
    Two-pass deduplication:
      1. Exact (case-insensitive, stripped)
      2. Fuzzy (SequenceMatcher ratio >= threshold)
    Returns (deduped_list, n_exact_removed, n_fuzzy_removed).
    """
    # ── Pass 1: exact ───────────────────────────────────────────────────
    seen: Dict[str, str] = {}  # lower → original form kept
    exact_deduped: List[str] = []
    n_exact = 0
    for kw in keywords:
        key = kw.lower().strip()
        if not key:
            continue
        if key in seen:
            n_exact += 1
        else:
            seen[key] = kw.strip()
            exact_deduped.append(kw.strip())

    # ── Pass 2: fuzzy ──────────────────────────────────────────────────
    if fuzzy_threshold >= 1.0:
        return exact_deduped, n_exact, 0

    kept: List[str] = []
    removed: Set[int] = set()
    n_fuzzy = 0
    for i, kw1 in enumerate(exact_deduped):
        if i in removed:
            continue
        kept.append(kw1)
        for j in range(i + 1, len(exact_deduped)):
            if j in removed:
                continue
            ratio = SequenceMatcher(None, kw1.lower(), exact_deduped[j].lower()).ratio()
            if ratio >= fuzzy_threshold:
                removed.add(j)
                n_fuzzy += 1

    return kept, n_exact, n_fuzzy


class KeywordsResearcherEngine:
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

    def get_suggestions(
        self,
        keywords: List[str],
        language: str = "fr",
        country_short: str = "FR",
        max_suggestions: int = 5,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Fetch Google Suggest for each keyword.
        Returns (suggest_keywords, combined_list) — combined = originals + new suggestions.
        """
        if not keywords:
            return [], list(keywords)

        if on_progress:
            on_progress("🔍 Récupération des suggestions Google…")

        original_set: Set[str] = {kw.lower().strip() for kw in keywords}
        suggest_keywords: List[str] = []

        suggest_map = self.suggest_client.get_suggestions_batch(
            keywords=keywords,
            language=language,
            country=country_short,
            max_results=max_suggestions,
            on_progress=lambda done, total, kw: (
                on_progress(f"Google Suggest : {done}/{total} — {kw}") if on_progress else None
            ),
        )
        seen_suggestions: Set[str] = set()
        for kw, suggestions in suggest_map.items():
            for s in suggestions:
                s_lower = s.lower().strip()
                if s_lower not in original_set and s_lower not in seen_suggestions:
                    seen_suggestions.add(s_lower)
                    suggest_keywords.append(s)

        combined = list(keywords) + suggest_keywords
        if on_progress:
            on_progress(
                f"✅ {len(suggest_keywords)} suggestions trouvées — "
                f"{len(combined)} mots-clés au total"
            )
        return suggest_keywords, combined

    def research_with_suggest(
        self,
        keywords: List[str],
        language: str = "fr",
        location_code: Optional[int] = None,
        country_short: str = "FR",
        max_suggestions: int = 5,
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

        original_set: Set[str] = {kw.lower().strip() for kw in keywords}
        _, combined = self.get_suggestions(
            keywords=keywords,
            language=language,
            country_short=country_short,
            max_suggestions=max_suggestions,
            on_progress=on_progress,
        )

        # ── Fetch volumes ───────────────────────────────────────────────
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

        # wait_for_task already calls get_task_result internally — use its
        # return value directly to avoid a second (possibly empty) fetch.
        raw = self.client.wait_for_task(task_id)
        if not raw:
            logger.error("Task %s timed out or returned no data", task_id)
            return []

        return self._parse_raw(raw)

    @staticmethod
    def _parse_raw(raw: List[dict]) -> List[KeywordVolumeResult]:
        """Convert flat dicts from DataForSEO into KeywordVolumeResult objects."""
        results: List[KeywordVolumeResult] = []
        for item in raw:
            ms = item.get("monthly_searches") or []
            results.append(
                KeywordVolumeResult(
                    keyword=item.get("keyword", ""),
                    search_volume=item.get("search_volume", 0),
                    competition=item.get("competition"),
                    cpc=item.get("cpc"),
                    monthly_searches=[
                        {"year": m.get("year"), "month": m.get("month"), "count": m.get("search_volume", 0)}
                        for m in ms
                    ],
                )
            )
        return results
