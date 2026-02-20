"""
Google Suggest API client.
Fetches autocomplete suggestions from Google.
"""

import logging
import time
from typing import Dict, List, Optional

import requests

from config.settings import GOOGLE_SUGGEST_URL, SUGGEST_TIMEOUT

logger = logging.getLogger(__name__)


class GoogleSuggestClient:
    """Fetch Google autocomplete suggestions."""

    def __init__(self, timeout: int = SUGGEST_TIMEOUT):
        self.timeout = timeout
        self.url = GOOGLE_SUGGEST_URL

    def get_suggestions(
        self,
        keyword: str,
        language: str,
        country: str,
        max_results: int = 9,
    ) -> List[str]:
        try:
            params = {"client": "firefox", "q": keyword, "hl": language, "gl": country}
            resp = requests.get(self.url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 1 and isinstance(data[1], list):
                    return data[1][:max_results]
            return []
        except Exception as e:
            logger.warning(f"Google Suggest error for '{keyword}': {e}")
            return []

    def get_suggestions_batch(
        self,
        keywords: List[str],
        language: str,
        country: str,
        delay: float = 0.1,
        on_progress: Optional[callable] = None,
    ) -> Dict[str, List[str]]:
        results = {}
        total = len(keywords)
        for idx, keyword in enumerate(keywords):
            suggestions = self.get_suggestions(keyword, language, country)
            results[keyword] = suggestions
            if on_progress:
                on_progress(idx + 1, total, keyword)
            if delay > 0 and idx < total - 1:
                time.sleep(delay)
        return results
