"""
Content Fetcher — downloads and extracts web page content.
Refactored from Scoring/content-analyzer/core/fetch.py
"""
import logging
import time
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── best HTML parser available ──────────────────────────────────────────────
def _best_parser() -> str:
    for p in ("lxml", "html.parser", "html5lib"):
        try:
            BeautifulSoup("<p>ok</p>", p)
            return p
        except Exception:
            continue
    return "html.parser"

PARSER = _best_parser()

# ── unwanted CSS patterns ───────────────────────────────────────────────────
_UNWANTED_TAGS = ("script", "style", "nav", "header", "footer", "aside")
_UNWANTED_PATTERNS = (
    "nav", "navigation", "menu", "sidebar", "footer", "header",
    "ad", "ads", "advertisement", "banner", "popup", "modal",
    "share", "social", "comment", "related", "cookie",
)
_MAIN_SELECTORS = (
    "main", "article", '[role="main"]', ".main-content",
    ".content", ".post-content", ".entry-content", ".article-content",
    "#main", "#content", "#article", ".container .content",
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class ContentFetcher:
    """Fetches and extracts content from web pages."""

    def __init__(self, timeout: int = 30, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
        })

    # ── public API ──────────────────────────────────────────────────────────

    def fetch_and_extract(self, url: str) -> Dict:
        """Download URL and return structured extraction result dict."""
        result: Dict = {
            "url": url, "title": "", "content": "", "lang_html": None,
            "meta_description": None, "status": "error", "error": None,
            "response_code": None, "word_count_before_clean": 0,
        }
        if not self._validate(url):
            result["error"] = "URL invalide"
            return result

        try:
            resp = self._get(url)
            if not resp:
                result["error"] = "Échec du téléchargement"
                return result
            result["response_code"] = resp.status_code
            soup = BeautifulSoup(resp.text, PARSER)
            result["title"] = self._extract_title(soup, url)
            result["content"] = self._extract_main(soup)
            result["lang_html"] = self._extract_lang(soup)
            result["meta_description"] = self._extract_meta(soup)
            result["word_count_before_clean"] = len(result["content"].split())
            result["status"] = "success" if len(result["content"]) >= 50 else "insufficient"
        except Exception as e:
            result["error"] = str(e)
            logger.error("fetch error %s: %s", url, e)
        return result

    # ── internals ───────────────────────────────────────────────────────────

    @staticmethod
    def _validate(url: str) -> bool:
        try:
            r = urlparse(url)
            return r.scheme in ("http", "https") and bool(r.netloc)
        except Exception:
            return False

    def _get(self, url: str) -> Optional[requests.Response]:
        for attempt in range(self.max_retries + 1):
            try:
                r = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                logger.warning("GET %s attempt %d: %s", url, attempt + 1, e)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        return None

    @staticmethod
    def _extract_title(soup: BeautifulSoup, url: str) -> str:
        for tag in (soup.find("title"), soup.find("meta", property="og:title"),
                    soup.find("h1"), soup.find("meta", attrs={"name": "title"})):
            if tag:
                txt = tag.get("content", None) or tag.get_text(strip=True)
                if txt:
                    return txt
        return url

    @staticmethod
    def _extract_lang(soup: BeautifulSoup) -> Optional[str]:
        html = soup.find("html")
        if html and html.get("lang"):
            return html["lang"].lower()
        for attr in ({"http-equiv": "content-language"}, {"name": "language"}):
            m = soup.find("meta", attrs=attr)
            if m and m.get("content"):
                return m["content"].lower()
        return None

    @staticmethod
    def _extract_meta(soup: BeautifulSoup) -> Optional[str]:
        for sel in ({"name": "description"}, {"property": "og:description"}):
            m = soup.find("meta", attrs=sel)
            if m and m.get("content"):
                return m["content"].strip()
        return None

    def _extract_main(self, soup: BeautifulSoup) -> str:
        copy = BeautifulSoup(str(soup), PARSER)
        self._remove_unwanted(copy)
        for sel in _MAIN_SELECTORS:
            try:
                el = copy.select_one(sel)
                if el:
                    t = el.get_text(separator=" ", strip=True)
                    if len(t) > 100:
                        return t
            except Exception:
                continue
        body = copy.find("body")
        return body.get_text(separator=" ", strip=True) if body else copy.get_text(separator=" ", strip=True)

    @staticmethod
    def _remove_unwanted(soup: BeautifulSoup) -> None:
        for tag in _UNWANTED_TAGS:
            for el in soup.find_all(tag):
                el.decompose()
        for pat in _UNWANTED_PATTERNS:
            for el in soup.find_all(class_=lambda x: x and any(pat in c.lower() for c in x)):
                el.decompose()
            for el in soup.find_all(id=lambda x: x and pat in x.lower()):
                el.decompose()
