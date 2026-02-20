"""
Seeds Loader — loads keyword seed templates from JSON files.
Refactored from Travel Agent V3/config/seeds_loader.py
"""
import json
import os
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CATEGORIES = ("dreamer", "planner", "booker", "concierge")


class SeedsLoader:
    """Load keyword seed templates per language and category."""

    def __init__(self, seeds_dir: Optional[str] = None):
        if seeds_dir is None:
            seeds_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config", "seeds",
            )
        self.seeds_dir = seeds_dir
        self._cache: Dict[str, Dict[str, List[str]]] = {}

    def available_languages(self) -> List[str]:
        if not os.path.isdir(self.seeds_dir):
            return []
        return sorted(f[:-5] for f in os.listdir(self.seeds_dir) if f.endswith(".json"))

    def load(self, lang: str) -> Dict[str, List[str]]:
        if lang in self._cache:
            return self._cache[lang]
        path = os.path.join(self.seeds_dir, f"{lang}.json")
        if not os.path.isfile(path):
            logger.warning("Seeds not found for %s, falling back to en", lang)
            path = os.path.join(self.seeds_dir, "en.json")
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            result = {cat: data.get(cat, []) for cat in CATEGORIES}
            self._cache[lang] = result
            return result
        except Exception as e:
            logger.error("load seeds %s: %s", path, e)
            return {}

    def flat(self, lang: str) -> List[Tuple[str, str]]:
        """All (seed, category) pairs."""
        return [(s, cat) for cat, seeds in self.load(lang).items() for s in seeds]

    def generate_keywords(self, lang: str, destinations: List[str], categories: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        Generate "{seed} {destination}" keywords.
        Returns {keyword: {destination, category}}.
        """
        seeds_by_cat = self.load(lang)
        cats = categories or list(seeds_by_cat.keys())
        out: Dict[str, Dict] = {}
        for dest in destinations:
            d = dest.lower().strip()
            for cat in cats:
                for seed in seeds_by_cat.get(cat, []):
                    kw = f"{seed} {d}".strip()
                    out[kw] = {"destination": d, "category": cat}
        return out
