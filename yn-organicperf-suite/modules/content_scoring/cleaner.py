"""
Content Cleaner — normalises and truncates extracted text.
Refactored from Scoring/content-analyzer/core/clean.py
"""
import re
import logging
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

try:
    from readability import Document          # readability-lxml
    _READABILITY = True
except ImportError:
    _READABILITY = False

logger = logging.getLogger(__name__)

_PARSER = "lxml" if True else "html.parser"   # overridden at import time
try:
    BeautifulSoup("<p>ok</p>", "lxml")
except Exception:
    _PARSER = "html.parser"


class ContentCleaner:
    """Normalise, deduplicate, and truncate web content."""

    def __init__(self, min_length: int = 100, chunk_size: int = 8000):
        self.min_length = min_length
        self.chunk_size = chunk_size

    # ── public API ──────────────────────────────────────────────────────────

    def clean(self, data: Dict) -> Dict:
        """Return enriched copy of *data* with cleaned content."""
        out = data.copy()
        if "title" in out:
            out["title_cleaned"] = self._clean_title(out["title"])
        if "content" in out:
            content = out["content"]
            if "html" in data and data["html"] and _READABILITY:
                rc = self._readability(data["html"], data.get("url", ""))
                if rc:
                    content = rc
            content = self._normalize(content)
            content = self._dedup_lines(content)
            content = self._truncate(content)
            out["content_cleaned"] = content
            out["content_length"] = len(content)
            out["content_words"] = len(content.split())
            out["word_count_after_clean"] = out["content_words"]
            out["content_sentences"] = len(self._sentences(content))
            out["content_type_detected"] = self._detect_type(content, out.get("title_cleaned", ""))
            out["content_sufficient"] = len(content) >= self.min_length
        return out

    # ── internals ───────────────────────────────────────────────────────────

    @staticmethod
    def _readability(html: str, url: str) -> Optional[str]:
        try:
            doc = Document(html)
            soup = BeautifulSoup(doc.summary(), _PARSER)
            txt = soup.get_text(separator=" ", strip=True)
            return txt if len(txt) > 100 else None
        except Exception as e:
            logger.debug("readability %s: %s", url, e)
            return None

    @staticmethod
    def _normalize(text: str) -> str:
        if not text:
            return ""
        for old, new in (("\u00a0", " "), ("\u2013", "-"), ("\u2014", "-"),
                         ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"')):
            text = text.replace(old, new)
        text = re.sub(r"\s+", " ", text)
        text = "\n".join(l.strip() for l in text.split("\n"))
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()

    @staticmethod
    def _dedup_lines(text: str) -> str:
        seen, out = set(), []
        for line in text.split("\n"):
            s = line.strip()
            if s and (s not in seen or len(s) <= 10):
                seen.add(s)
                out.append(s)
        return "\n".join(out)

    def _truncate(self, text: str) -> str:
        if len(text) <= self.chunk_size:
            return text
        result = ""
        for s in self._sentences(text):
            if len(result) + len(s) + 2 > self.chunk_size:
                break
            result += s + ". "
        return result.strip()

    @staticmethod
    def _sentences(text: str) -> List[str]:
        return [s.strip() for s in re.split(r"[.!?]+(?:\s|$)", text) if len(s.strip()) > 10]

    @staticmethod
    def _clean_title(title: str) -> str:
        if not title:
            return ""
        for pat in (r"\s*[-|•]\s*[^-|•]*$", r"^\s*[^-|•]*\s*[-|•]\s*"):
            m = re.search(pat, title)
            if m:
                title = re.sub(pat, "", title)
                break
        title = re.sub(r"\s+", " ", title).strip()
        return title[:97] + "..." if len(title) > 100 else title

    @staticmethod
    def _detect_type(text: str, title: str) -> str:
        low = (text + " " + title).lower()
        if any(w in low for w in ("acheter", "prix", "commande", "panier", "buy", "price", "order")):
            return "transactional"
        if any(w in low for w in ("comment", "pourquoi", "qu'est-ce", "guide", "tutorial")):
            return "informational"
        if any(w in low for w in ("avis", "test", "review", "expérience")):
            return "experience"
        return "informational"
