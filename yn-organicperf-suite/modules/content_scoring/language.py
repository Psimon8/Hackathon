"""
Language Detector — determines the page language from HTML + content.
Refactored from Scoring/content-analyzer/core/lang.py
"""
import re
import logging
from typing import Dict, Optional, Tuple

try:
    from langdetect import detect_langs           # type: ignore
    _LANGDETECT = True
except ImportError:
    _LANGDETECT = False

logger = logging.getLogger(__name__)

SUPPORTED = {
    "fr": "FR", "de": "DE", "es": "ES", "en": "EN",
    "ja": "JA", "pt": "PT-BR", "pt-br": "PT-BR",
}

LABELS = {
    "auto": "Automatique", "FR": "Français", "DE": "Deutsch",
    "ES": "Español", "EN": "English", "JA": "日本語", "PT-BR": "Português (BR)",
}

_KEYWORDS: Dict[str, list] = {
    "FR": ["le", "la", "les", "une", "des", "dans", "pour", "avec", "sur", "par", "est", "sont", "que", "qui", "où"],
    "DE": ["der", "die", "das", "und", "ist", "sind", "mit", "für", "auf", "von", "zu", "bei", "nach", "über"],
    "ES": ["el", "la", "los", "las", "una", "con", "por", "para", "en", "de", "que", "es", "son", "como"],
    "EN": ["the", "and", "for", "are", "with", "this", "that", "from", "they", "have", "had", "you", "can"],
    "JA": ["です", "である", "します", "これ", "それ", "ここ", "この", "その"],
    "PT-BR": ["para", "com", "por", "são", "uma", "que", "não", "mais", "como", "seu", "sua", "você"],
}

_DIRECT = {
    "fr": "FR", "fr-fr": "FR", "de": "DE", "de-de": "DE",
    "es": "ES", "es-es": "ES", "en": "EN", "en-us": "EN", "en-gb": "EN",
    "ja": "JA", "ja-jp": "JA", "pt": "PT-BR", "pt-br": "PT-BR",
}


class LanguageDetector:
    """Detects the language of page content."""

    def determine(
        self,
        html_lang: Optional[str] = None,
        content: str = "",
        title: str = "",
        forced: Optional[str] = None,
    ) -> Tuple[str, str, float]:
        """Return (lang_code, method, confidence)."""
        if forced and forced in SUPPORTED.values():
            return forced, "forced", 1.0
        norm = self._norm(html_lang) if html_lang else None
        if norm:
            cd = self._detect_content(content)
            if cd and cd[0] == norm:
                return norm, "html_confirmed", cd[1]
            if not cd or cd[1] < 0.7:
                return norm, "html", 0.8
        cd = self._detect_content(content)
        if cd and cd[1] > 0.7:
            return cd[0], "content", cd[1]
        kw = self._detect_keywords(content, title)
        if kw:
            return kw, "keywords", 0.6
        if norm:
            return norm, "html_fallback", 0.5
        return "EN", "default", 0.3

    def analyze(self, data: Dict, forced: Optional[str] = None) -> Dict:
        """Enrich *data* with language fields."""
        out = data.copy()
        code, method, conf = self.determine(
            html_lang=data.get("lang_html"),
            content=data.get("content_cleaned", data.get("content", "")),
            title=data.get("title_cleaned", data.get("title", "")),
            forced=forced,
        )
        out.update({
            "language_final": code,
            "language_detection_method": method,
            "language_confidence": conf,
            "language_label": LABELS.get(code, code),
            "language_for_prompt": code,
        })
        return out

    # ── internals ───────────────────────────────────────────────────────────

    @staticmethod
    def _norm(lang: str) -> Optional[str]:
        return _DIRECT.get(lang.lower().strip())

    @staticmethod
    def _detect_content(text: str) -> Optional[Tuple[str, float]]:
        if not _LANGDETECT or not text or len(text.strip()) < 50:
            return None
        try:
            best = detect_langs(text)[0]
            mapped = SUPPORTED.get(best.lang)
            if mapped:
                return mapped, best.prob
        except Exception:
            pass
        return None

    @staticmethod
    def _detect_keywords(text: str, title: str) -> Optional[str]:
        full = (text + " " + title).lower()
        scores = {lang: sum(1 for w in words if w in full) for lang, words in _KEYWORDS.items()}
        if scores:
            best = max(scores, key=scores.get)
            if scores[best] >= 3:
                return best
        return None
