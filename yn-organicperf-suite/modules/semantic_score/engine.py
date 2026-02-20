"""
Semantic Score Engine — orchestrates keyword-level analysis.
Refactored from Score Sémantique / core/engine.py — no Tkinter/threading; pure async.
"""

import asyncio
import functools
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple

from core.dataforseo_client import DataForSEOClient
from core.models import IndividualURLResult, SemanticScoreResult
from config.settings import COUNTRY_CODES, DEFAULT_BERT_THRESHOLD, DEFAULT_LEVENSHTEIN_THRESHOLD
from modules.semantic_score.text_analysis import TextAnalyzer
from modules.semantic_score.gpt_refiner import SemanticGPTRefiner

logger = logging.getLogger(__name__)


class SemanticScoreEngine:
    """Orchestrates keyword semantic analysis (no GUI dependency)."""

    def __init__(self, language: str = "fr"):
        self.api_client = DataForSEOClient()
        self.text_analyzer = TextAnalyzer(language=language)
        self.gpt_refiner = SemanticGPTRefiner()

    # ═══════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════

    def analyze_keywords(
        self,
        keywords: List[str],
        domain: str,
        country: str,
        language: str,
        num_urls: int = 10,
        bert_threshold: float = DEFAULT_BERT_THRESHOLD,
        lev_threshold: float = DEFAULT_LEVENSHTEIN_THRESHOLD,
        use_onpage: bool = True,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[SemanticScoreResult]:
        """
        Blocking entry point: run the async analysis loop and return results.
        Suitable for Streamlit (call from synchronous context).
        """
        return asyncio.run(
            self._async_analyze_all(
                keywords, domain, country, language,
                num_urls, bert_threshold, lev_threshold,
                use_onpage, on_progress,
            )
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Internal async orchestration
    # ═══════════════════════════════════════════════════════════════════════

    async def _async_analyze_all(
        self,
        keywords: List[str],
        domain: str,
        country: str,
        language: str,
        num_urls: int,
        bert_threshold: float,
        lev_threshold: float,
        use_onpage: bool,
        on_progress: Optional[Callable],
    ) -> List[SemanticScoreResult]:
        country_code = COUNTRY_CODES.get(country.upper(), COUNTRY_CODES.get("FR", 2250))
        results: List[SemanticScoreResult] = []

        for idx, kw in enumerate(keywords, 1):
            if on_progress:
                on_progress(idx, len(keywords), kw)
            try:
                r = await self._analyze_keyword(
                    kw, domain, country_code, language,
                    num_urls, bert_threshold, lev_threshold, use_onpage,
                )
                results.append(r)
            except Exception as e:
                logger.error(f"Error analyzing '{kw}': {e}", exc_info=True)
                r = SemanticScoreResult(keyword=kw, error=str(e))
                results.append(r)

        await self.api_client.close()
        return results

    async def _analyze_keyword(
        self,
        keyword: str,
        domain: str,
        country_code: int,
        language: str,
        num_urls: int,
        bert_thresh: float,
        lev_thresh: float,
        use_onpage: bool,
    ) -> SemanticScoreResult:
        start = time.monotonic()
        result = SemanticScoreResult(keyword=keyword)
        loop = asyncio.get_running_loop()

        # 1 — SERP search
        search_items = await self.api_client.search_organic_async(
            keyword=keyword, language=language, country=country_code, num_results=num_urls,
        )
        if not search_items:
            result.error = "No search results found."
            result.analysis_time = time.monotonic() - start
            return result

        organic_items = [i for i in search_items if i.get("type") == "organic" and i.get("url")]
        urls_to_parse = [i.get("url") for i in organic_items]

        # Find domain URL
        domain_url: Optional[str] = None
        if domain:
            for item in organic_items:
                u = item.get("url", "")
                if domain.lower() in u.lower():
                    domain_url = u
                    break

        # 2 — Fetch & parse all URLs
        url_data, competitor_contents, domain_content_data, success_count = (
            await self._fetch_all(urls_to_parse, domain_url, use_onpage)
        )

        texts_for_scoring = url_data.pop("_texts", [])
        url_order = url_data.pop("_url_order", [])

        if not texts_for_scoring:
            result.error = "Could not retrieve content for any URL."
            for item in search_items:
                u, pos = item.get("url"), item.get("rank_absolute")
                if u and pos is not None:
                    result.top_results.append(IndividualURLResult(url=u, position=pos, title=item.get("title")))
            result.top_results.sort(key=lambda x: x.position)
            result.analysis_time = time.monotonic() - start
            return result

        # 3 — SEO-weighted scores per URL
        for url in url_order:
            if url in url_data:
                d = url_data[url]
                score = await loop.run_in_executor(
                    None,
                    functools.partial(
                        self.text_analyzer.calculate_seo_weighted_score,
                        keyword,
                        title=d.get("title"),
                        h1=d.get("h1"),
                        meta_description=d.get("meta_description"),
                        h2_tags=d.get("h2_tags", []),
                        h3_tags=d.get("h3_tags", []),
                        body_content=d.get("content"),
                    ),
                )
                url_data[url]["score"] = score

        # 4 — Populate individual results
        self._populate_results(result, search_items, url_data, domain_url)

        # 5 — Domain-specific analysis
        if domain_url and domain_content_data:
            await self._analyze_domain(
                result, keyword, domain_url, domain_content_data,
                search_items, url_data, bert_thresh, lev_thresh,
            )
        elif domain:
            result.domain_url = f"Domain '{domain}' not found in Top {num_urls}"

        # 6 — Competitor n-grams
        await self._analyze_competitor_ngrams(result, keyword, competitor_contents, bert_thresh, lev_thresh)

        # 7 — N-gram differential
        self._calculate_diff(result)

        # 8 — GPT refine n-grams
        try:
            result.refined_ngrams = self.gpt_refiner.refine_ngrams(
                keyword=keyword,
                domain_ngrams=result.domain_ngrams,
                competitor_ngrams=result.average_competitor_ngrams,
                ngram_differential=result.ngram_differential,
            )
        except Exception as e:
            logger.warning(f"GPT n-gram refinement failed for '{keyword}': {e}")
            result.refined_ngrams = None

        # 9 — GPT generate SEO brief
        try:
            result.seo_brief = self.gpt_refiner.generate_seo_brief(
                keyword=keyword,
                refined_ngrams=result.refined_ngrams,
                competitors=result.top_results,
            )
        except Exception as e:
            logger.warning(f"GPT SEO brief generation failed for '{keyword}': {e}")
            result.seo_brief = None

        result.analysis_time = time.monotonic() - start
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════════

    async def _fetch_all(
        self, urls: List[str], domain_url: Optional[str], use_onpage: bool
    ) -> Tuple[Dict, Dict, Optional[Tuple], int]:
        url_data: Dict = {}
        texts: List[str] = []
        url_order: List[str] = []
        competitor_contents: Dict[str, str] = {}
        domain_data = None
        ok = 0

        tasks = {u: asyncio.create_task(self.api_client.parse_content(u, use_onpage)) for u in urls}

        for url, task in tasks.items():
            is_dom = url == domain_url
            try:
                res = await task
                if isinstance(res, tuple) and len(res) == 7:
                    content, h1, title, meta, h2, h3, method = res
                    if content:
                        ok += 1
                        texts.append(content)
                        url_order.append(url)
                        if not is_dom:
                            competitor_contents[url] = content
                    if is_dom:
                        domain_data = (content, h1, title, meta, h2, h3)
                    url_data[url] = {
                        "content": content, "h1": h1, "title": title,
                        "meta_description": meta, "h2_tags": h2, "h3_tags": h3,
                        "score": None, "scrape_method": method,
                    }
                else:
                    url_data[url] = self._empty_url_data()
            except Exception as e:
                logger.error(f"Fetch error {url}: {e}")
                url_data[url] = self._empty_url_data()

        url_data["_texts"] = texts
        url_data["_url_order"] = url_order
        return url_data, competitor_contents, domain_data, ok

    @staticmethod
    def _empty_url_data() -> Dict:
        return {
            "content": None, "h1": None, "title": None,
            "meta_description": None, "h2_tags": [], "h3_tags": [],
            "score": None, "scrape_method": "failed",
        }

    def _populate_results(self, result, search_items, url_data, domain_url):
        all_scores, comp_scores = [], []
        for item in search_items:
            url = item.get("url")
            pos = item.get("rank_absolute")
            if not url or url not in url_data or pos is None:
                continue
            d = url_data[url]
            if not isinstance(d, dict):
                continue
            score = d.get("score")
            content = d.get("content")
            wc = len(content.split()) if content else 0
            result.top_results.append(
                IndividualURLResult(
                    url=url, position=pos, title=d.get("title") or item.get("title"),
                    meta_description=d.get("meta_description"),
                    semantic_score=score, h1=d.get("h1"),
                    h2_tags=d.get("h2_tags", []), h3_tags=d.get("h3_tags", []),
                    body_content=content, word_count=wc,
                    scrape_method=d.get("scrape_method", "failed"),
                )
            )
            is_dom = url == domain_url
            if score is not None:
                all_scores.append(score)
                if not is_dom:
                    comp_scores.append(score)

        result.top_results.sort(key=lambda x: x.position)
        result.average_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
        result.average_competitor_score = sum(comp_scores) / len(comp_scores) if comp_scores else 0.0

    async def _analyze_domain(self, result, keyword, domain_url, domain_data, search_items, url_data, bt, lt):
        loop = asyncio.get_running_loop()
        content, h1, title, meta, h2, h3 = domain_data
        serp_item = next((i for i in search_items if i.get("url") == domain_url), None)
        result.domain_position = serp_item.get("rank_absolute") if serp_item else None
        result.domain_url = domain_url
        result.domain_score = url_data.get(domain_url, {}).get("score") if isinstance(url_data.get(domain_url), dict) else None
        result.domain_content = content
        result.domain_h1 = h1
        result.domain_title = title

        if content:
            _, ng, raw = await loop.run_in_executor(
                None, functools.partial(
                    self.text_analyzer.get_significant_ngrams, content, keyword,
                    bert_threshold=bt, lev_threshold=lt,
                ),
            )
            result.domain_ngrams = ng or {}
            result.raw_ngrams_context = raw or {}
            result.keyword_density = await loop.run_in_executor(
                None, functools.partial(self.text_analyzer.calculate_keyword_density, content, keyword),
            )
            result.faq_questions = await loop.run_in_executor(
                None, functools.partial(self.text_analyzer.extract_questions, content),
            )

    async def _analyze_competitor_ngrams(self, result, keyword, comp_contents, bt, lt):
        loop = asyncio.get_running_loop()
        all_freq: Dict[str, Dict[str, float]] = {"unigrams": {}, "bigrams": {}, "trigrams": {}}
        combined_raw: Dict[str, Dict[str, int]] = {"unigrams": {}, "bigrams": {}, "trigrams": {}}

        tasks_list = [
            loop.run_in_executor(
                None, functools.partial(
                    self.text_analyzer.get_significant_ngrams, c, keyword,
                    bert_threshold=bt, lev_threshold=lt,
                ),
            )
            for c in comp_contents.values()
        ]
        if not tasks_list:
            result.average_competitor_ngrams = {}
            return

        ngram_results = await asyncio.gather(*tasks_list)
        count = len(ngram_results)
        for _, ng, raw in ngram_results:
            if ng:
                for t, phrases in ng.items():
                    for p, f in phrases.items():
                        all_freq.setdefault(t, {})[p] = all_freq.get(t, {}).get(p, 0) + f
            if raw:
                for t, phrases in raw.items():
                    for p, f in phrases.items():
                        combined_raw.setdefault(t, {})[p] = combined_raw.get(t, {}).get(p, 0) + f

        result.average_competitor_ngrams = {
            t: {p: total / count for p, total in phrases.items()}
            for t, phrases in all_freq.items()
        }
        if not result.raw_ngrams_context and any(combined_raw.values()):
            result.raw_ngrams_context = combined_raw

    @staticmethod
    def _calculate_diff(result):
        if not result.domain_ngrams or not result.average_competitor_ngrams:
            result.ngram_differential = None
            return
        result.ngram_differential = {}
        all_types = set(result.domain_ngrams) | set(result.average_competitor_ngrams)
        for t in all_types:
            dom = result.domain_ngrams.get(t, {})
            avg = result.average_competitor_ngrams.get(t, {})
            all_p = set(dom) | set(avg)
            result.ngram_differential[t] = {
                p: dom.get(p, 0) - avg.get(p, 0) for p in all_p
            }
