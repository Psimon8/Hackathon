"""
Unified DataForSEO client.
Covers SERP searches, OnPage content parsing, and Keyword Volume endpoints.
"""

import asyncio
import base64
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import aiohttp
import requests
import trafilatura
from bs4 import BeautifulSoup

from core.cache import Cache
from core.credentials import get_credentials
from config.settings import (
    DATAFORSEO_BASE_URL,
    DATAFORSEO_SERP_ENDPOINT,
    DATAFORSEO_ONPAGE_ENDPOINT,
    DATAFORSEO_KEYWORDS_POST,
    DATAFORSEO_KEYWORDS_READY,
    DATAFORSEO_KEYWORDS_GET,
    MAX_KEYWORDS_PER_BATCH,
    REQUEST_TIMEOUT,
    RETRY_DELAY,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class DataForSEOClient:
    """Unified client for all DataForSEO API endpoints."""

    def __init__(self):
        creds = get_credentials()
        self.login = creds.dataforseo_login
        self.password = creds.dataforseo_password
        self.base_url = DATAFORSEO_BASE_URL

        credentials = f"{self.login}:{self.password}"
        self.encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        self.headers = {
            "Authorization": f"Basic {self.encoded_credentials}",
            "Content-Type": "application/json",
        }

        self.cache = Cache()
        self._session: Optional[aiohttp.ClientSession] = None
        self.request_timestamps: List[float] = []
        self.daily_requests = 0

    # ── Async session management ─────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ── Rate limiting ────────────────────────────────────────────────────

    async def _rate_limit(self):
        now = time.time()
        self.request_timestamps = [t for t in self.request_timestamps if now - t <= 60]
        if len(self.request_timestamps) >= 30:  # 30 req/min
            wait = 60.0 - (now - self.request_timestamps[0]) + 0.1
            if wait > 0:
                await asyncio.sleep(wait)

    # ── Low-level async request ──────────────────────────────────────────

    async def _async_request(self, url: str, data: List[Dict]) -> Optional[Dict]:
        await self._rate_limit()
        session = await self._get_session()
        headers = {
            "Authorization": f"Basic {self.encoded_credentials}",
            "Content-Type": "application/json",
        }
        try:
            async with session.post(
                url, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                text = await response.text()
                if response.status == 200:
                    self.request_timestamps.append(time.time())
                    self.daily_requests += 1
                    return json.loads(text)
                logger.error(f"API Error {response.status}: {text[:300]}")
                return None
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # SERP — Google Organic Live Advanced
    # ═══════════════════════════════════════════════════════════════════════

    def search_serp_sync(
        self,
        keywords: List[str],
        country_code: int,
        language_code: str,
        depth: int = 10,
        on_progress=None,
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Synchronous SERP search (for Streamlit usage).
        Returns (organic_results, paa_results, kg_results) as list of dicts.
        """
        url = f"{self.base_url}{DATAFORSEO_SERP_ENDPOINT}"
        organic_results = []
        paa_results = []
        kg_results = []

        for idx, keyword in enumerate(keywords, 1):
            if on_progress:
                on_progress(idx, len(keywords), keyword)

            payload = [
                {
                    "keyword": keyword.strip(),
                    "location_code": country_code,
                    "language_code": language_code,
                    "device": "desktop",
                    "os": "windows",
                    "depth": depth,
                    "group_organic_results": True,
                    "load_async_ai_overview": False,
                    "people_also_ask_click_depth": 2,
                }
            ]

            try:
                resp = requests.post(url, headers=self.headers, json=payload, timeout=REQUEST_TIMEOUT)
                data = resp.json()

                if data.get("tasks"):
                    for task in data["tasks"]:
                        if task.get("result"):
                            for result in task["result"]:
                                check_url = result.get("check_url", "")
                                for item in result.get("items", []):
                                    if item["type"] == "organic":
                                        domain = urlparse(item.get("url", "")).netloc
                                        organic_results.append(
                                            {
                                                "keyword": keyword.strip(),
                                                "rank": item.get("rank_group"),
                                                "domain": domain,
                                                "title": item.get("title"),
                                                "url": item.get("url"),
                                                "description": item.get("description"),
                                            }
                                        )
                                    elif item["type"] == "people_also_ask":
                                        if "items" in item:
                                            for paa_item in item["items"]:
                                                if paa_item["type"] == "people_also_ask_element":
                                                    expanded_data = {}
                                                    if "expanded_element" in paa_item and paa_item["expanded_element"]:
                                                        exp = paa_item["expanded_element"][0]
                                                        expanded_data = {
                                                            "domain": exp.get("domain", ""),
                                                            "expanded_url": exp.get("url", ""),
                                                            "expanded_title": exp.get("title", ""),
                                                            "expanded_description": exp.get("description", ""),
                                                        }
                                                    paa_results.append(
                                                        {
                                                            "keyword": keyword.strip(),
                                                            "question": paa_item.get("title", ""),
                                                            "domain": expanded_data.get("domain", ""),
                                                            "url": expanded_data.get("expanded_url", ""),
                                                            "answer_title": expanded_data.get("expanded_title", ""),
                                                            "answer_description": expanded_data.get("expanded_description", ""),
                                                        }
                                                    )
                                    elif item["type"] == "knowledge_graph":
                                        kg_results.append(
                                            {
                                                "keyword": keyword.strip(),
                                                "check_url": check_url,
                                                "knowledge_graph_url": item.get("url", ""),
                                                "title": item.get("title", ""),
                                                "subtitle": item.get("subtitle", ""),
                                                "description": item.get("description", ""),
                                                "rank_group": item.get("rank_group", ""),
                                                "position": item.get("position", ""),
                                            }
                                        )
            except Exception as e:
                logger.error(f"Error processing keyword '{keyword}': {e}")

        return organic_results, paa_results, kg_results

    # ═══════════════════════════════════════════════════════════════════════
    # SERP — Async version (used by Semantic Score engine)
    # ═══════════════════════════════════════════════════════════════════════

    async def search_organic_async(
        self, keyword: str, language: str, country: int, num_results: int
    ) -> Optional[List[Dict]]:
        cache_key = f"search_{keyword}_{language}_{country}_{num_results}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        url = f"{self.base_url}{DATAFORSEO_SERP_ENDPOINT}"
        post_data = [
            {
                "language_code": language,
                "location_code": country,
                "keyword": keyword,
                "depth": num_results,
            }
        ]

        resp = await self._async_request(url, post_data)
        if resp and resp.get("status_code") == 20000:
            tasks = resp.get("tasks", [])
            if tasks and tasks[0].get("status_code") == 20000:
                results = tasks[0].get("result", [])
                if results and results[0].get("items"):
                    items = results[0]["items"]
                    self.cache.set(cache_key, items)
                    return items
                return []
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # OnPage Content Parsing
    # ═══════════════════════════════════════════════════════════════════════

    async def get_onpage_content(self, url_to_parse: str):
        """Returns (content, h1, title, meta_description, h2_tags, h3_tags) or None."""
        api_url = f"{self.base_url}{DATAFORSEO_ONPAGE_ENDPOINT}"
        post_data = [
            {
                "url": url_to_parse,
                "disable_cookie_popup": True,
                "enable_xhr": False,
                "switch_pool": True,
                "enable_javascript": False,
                "enable_browser_rendering": False,
            }
        ]
        resp = await self._async_request(api_url, post_data)

        texts = []
        h1 = None
        title = None
        meta_desc = None
        h2_tags: List[str] = []
        h3_tags: List[str] = []

        if resp and resp.get("status_code") == 20000:
            tasks = resp.get("tasks", [])
            if tasks and tasks[0].get("status_code") == 20000:
                results = tasks[0].get("result", [])
                if results and results[0].get("items"):
                    items = results[0]["items"]
                    if items and items[0].get("page_content"):
                        pc = items[0]["page_content"]
                        for topic in pc.get("main_topic", []):
                            if topic.get("h_title") and not h1:
                                h1 = topic["h_title"].strip()
                            if topic.get("main_title") and not title:
                                title = topic["main_title"].strip()
                        for tk in ("main_topic", "secondary_topic"):
                            for topic in pc.get(tk, []):
                                for item in topic.get("primary_content", []):
                                    if item.get("text"):
                                        texts.append(item["text"].strip())
                        content = " ".join(texts).strip() if texts else None
                        return (content, h1, title, meta_desc, h2_tags, h3_tags)
        return None

    async def parse_content(self, url: str, use_onpage_api: bool = True):
        """
        Parse page content. Strategy: homemade first, then OnPage API fallback.
        Returns (content, h1, title, meta_desc, h2, h3, method_used).
        """
        method = "failed"

        # Try homemade scraping
        try:
            result = await self._fetch_page_homemade(url)
            if result and result[0]:
                return (*result, "homemade")
        except Exception as e:
            logger.warning(f"Homemade scraping failed for {url}: {e}")

        # Fallback: OnPage API
        if use_onpage_api:
            try:
                result = await self.get_onpage_content(url)
                if result:
                    return (*result, "onpage")
            except Exception as e:
                logger.error(f"OnPage API failed for {url}: {e}")

        return (None, None, None, None, [], [], "failed")

    async def _fetch_page_homemade(self, url: str):
        """Fetch with trafilatura + BeautifulSoup. Returns (content, h1, title, meta, h2, h3)."""
        session = await self._get_session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=30), headers=headers, allow_redirects=True
            ) as response:
                response.raise_for_status()
                html = await response.text()

            text_content = trafilatura.extract(html, include_comments=False, include_tables=False)
            if text_content:
                text_content = re.sub(r"\s+", " ", text_content).strip()

            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else None
            meta_tag = soup.find("meta", attrs={"name": "description"})
            meta = meta_tag.get("content", "").strip() if meta_tag else None
            h1_tag = soup.find("h1")
            h1 = h1_tag.get_text(strip=True) if h1_tag else None
            h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all("h2")][:10]
            h3_tags = [h3.get_text(strip=True) for h3 in soup.find_all("h3")][:10]

            return (text_content, h1, title, meta, h2_tags, h3_tags)
        except Exception as e:
            logger.error(f"Fetch error for {url}: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # Keywords Data — Search Volume (3-step: post → ready → get)
    # ═══════════════════════════════════════════════════════════════════════

    def post_keyword_volume_task(
        self,
        keywords: List[str],
        location_code: Optional[int] = None,
        language_code: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Optional[str]:
        """Post a keyword volume task. Returns task_id."""
        url = f"{self.base_url}{DATAFORSEO_KEYWORDS_POST}"
        keywords = [self._sanitize_keyword(kw) for kw in keywords[:MAX_KEYWORDS_PER_BATCH]]
        keywords = [kw for kw in keywords if len(kw.split()) <= 10]
        if not keywords:
            return None

        payload_data: Dict[str, Any] = {"keywords": keywords, "sort_by": "search_volume"}
        if location_code:
            payload_data["location_code"] = location_code
        if language_code:
            payload_data["language_code"] = language_code
        if date_from:
            payload_data["date_from"] = date_from
        if date_to:
            payload_data["date_to"] = date_to

        try:
            resp = requests.post(url, headers=self.headers, json=[payload_data], timeout=REQUEST_TIMEOUT)
            data = resp.json()
            if data.get("status_code") == 20000:
                tasks = data.get("tasks", [])
                if tasks and tasks[0].get("id"):
                    return tasks[0]["id"]
        except Exception as e:
            logger.error(f"Error posting keyword task: {e}")
        return None

    def get_tasks_ready(self) -> Set[str]:
        url = f"{self.base_url}{DATAFORSEO_KEYWORDS_READY}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            data = resp.json()
            ready = set()
            if data.get("status_code") == 20000:
                tasks = data.get("tasks", [])
                if tasks:
                    for item in tasks[0].get("result", []) or []:
                        if item.get("id"):
                            ready.add(item["id"])
            return ready
        except Exception as e:
            logger.error(f"Error checking tasks_ready: {e}")
            return set()

    def get_task_result(self, task_id: str) -> Optional[List[Dict]]:
        url = f"{self.base_url}{DATAFORSEO_KEYWORDS_GET}/{task_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            data = resp.json()
            if data.get("status_code") == 20000:
                tasks = data.get("tasks", [])
                if tasks and tasks[0].get("status_code") == 20000:
                    result = tasks[0].get("result", [])
                    return self._flatten_keyword_results(result) if result else []
        except Exception as e:
            logger.error(f"Error getting task result: {e}")
        return None

    def wait_for_task(self, task_id: str, on_progress=None) -> Optional[List[Dict]]:
        """Poll until task is ready, then fetch results."""
        for attempt in range(MAX_RETRIES):
            if on_progress:
                on_progress(attempt + 1, MAX_RETRIES)
            ready_ids = self.get_tasks_ready()
            if task_id in ready_ids:
                return self.get_task_result(task_id)
            time.sleep(RETRY_DELAY)
        logger.error(f"Task {task_id} did not complete after {MAX_RETRIES} attempts")
        return None

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_keyword(kw: str) -> str:
        kw = kw.strip()
        kw = re.sub(r"[^\w\s\-'àâäéèêëïîôùûüÿçœæ]", "", kw, flags=re.UNICODE)
        return " ".join(kw.split())

    @staticmethod
    def _flatten_keyword_results(results: List[Dict]) -> List[Dict]:
        flat = []
        for r in results:
            for kw_data in r.get("result", []) if isinstance(r, dict) else []:
                flat.append(
                    {
                        "keyword": kw_data.get("keyword", ""),
                        "search_volume": kw_data.get("search_volume"),
                        "competition": kw_data.get("competition"),
                        "cpc": kw_data.get("cpc"),
                        "monthly_searches": kw_data.get("monthly_searches", []),
                    }
                )
        return flat
