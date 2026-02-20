"""
Text analysis — BERT embeddings, n-gram extraction, SEO-weighted scoring.
Refactored from Score Sémantique / text_analysis.py — no Tkinter dependency.
"""

import logging
import pathlib
import re
import unicodedata
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

import nltk
import numpy as np
import torch
from Levenshtein import distance as levenshtein_distance
from nltk.corpus import stopwords
from nltk.util import ngrams
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel

from config.settings import (
    DEFAULT_BERT_THRESHOLD,
    DEFAULT_LEVENSHTEIN_THRESHOLD,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_N,
    MIN_WORD_LENGTH,
    QUESTION_PATTERNS,
)

logger = logging.getLogger(__name__)

# terms_to_exclude lives at project root
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
TERMS_FILE_PATH = PROJECT_ROOT / "terms_to_exclude.txt"


class TextAnalyzer:
    """NLP text analyzer with BERT and sentence-transformer embeddings."""

    def __init__(self, language: str = "fr"):
        self.language = language.lower()
        self._ensure_nltk()
        self.stop_words = set(
            stopwords.words("french" if self.language == "fr" else "english")
        )
        self.similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD
        self.terms_to_exclude = self._load_terms_to_exclude()

        # Sentence-transformer for semantic scoring
        self.embedding_model = SentenceTransformer(
            "paraphrase-multilingual-mpnet-base-v2"
        )

        # BERT for n-gram relevance filtering
        try:
            self.bert_tokenizer = AutoTokenizer.from_pretrained(
                "bert-base-multilingual-cased"
            )
            self.bert_model = AutoModel.from_pretrained("bert-base-multilingual-cased")
            self.bert_device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
            self.bert_model.to(self.bert_device)
            logger.info(f"BERT model loaded on {self.bert_device}.")
        except Exception as e:
            logger.error(f"BERT load failed: {e}. N-gram filtering disabled.")
            self.bert_tokenizer = None
            self.bert_model = None
            self.bert_device = None

    # ── Static helpers ───────────────────────────────────────────────────

    @staticmethod
    def _ensure_nltk():
        for res in ("stopwords", "punkt"):
            try:
                nltk.data.find(f"tokenizers/{res}")
            except LookupError:
                nltk.download(res, quiet=True)

    def _load_terms_to_exclude(self) -> Set[str]:
        try:
            with open(TERMS_FILE_PATH, "r", encoding="utf-8") as f:
                return {line.strip().lower() for line in f if line.strip()}
        except FileNotFoundError:
            logger.warning(f"{TERMS_FILE_PATH} not found. No terms excluded.")
            return set()

    # ── BERT embeddings ──────────────────────────────────────────────────

    def _bert_embed(self, text: str) -> Optional[np.ndarray]:
        if not self.bert_model:
            return None
        try:
            inputs = self.bert_tokenizer(
                text, return_tensors="pt", truncation=True, max_length=512, padding=True
            ).to(self.bert_device)
            with torch.no_grad():
                outputs = self.bert_model(**inputs)
            return outputs.last_hidden_state[0, 0, :].cpu().numpy()
        except Exception as e:
            logger.error(f"BERT embed error: {e}")
            return None

    def _bert_embed_batch(self, texts: List[str]) -> Optional[np.ndarray]:
        if not self.bert_model or not texts:
            return None
        try:
            inputs = self.bert_tokenizer(
                texts, return_tensors="pt", truncation=True, max_length=512, padding=True
            ).to(self.bert_device)
            with torch.no_grad():
                outputs = self.bert_model(**inputs)
            return outputs.last_hidden_state[:, 0, :].cpu().numpy()
        except Exception as e:
            logger.error(f"BERT batch embed error: {e}")
            return None

    # ── N-gram filtering ─────────────────────────────────────────────────

    def _filter_ngrams_by_relevance(
        self,
        ngrams_dict: Dict[str, Dict[str, int]],
        keyword_embedding: np.ndarray,
        threshold: float = 0.5,
    ) -> Dict[str, Dict[str, int]]:
        if not self.bert_model or keyword_embedding is None:
            return ngrams_dict

        filtered: Dict[str, Dict[str, int]] = {"unigrams": {}, "bigrams": {}, "trigrams": {}}
        kw_emb = keyword_embedding.reshape(1, -1)

        for ng_type, phrases in ngrams_dict.items():
            if not phrases:
                continue
            pl = list(phrases.keys())
            pe = self._bert_embed_batch(pl)
            if pe is None:
                filtered[ng_type] = phrases
                continue
            try:
                sims = cosine_similarity(kw_emb, pe)[0]
            except ValueError:
                filtered[ng_type] = phrases
                continue
            for i, score in enumerate(sims):
                if score >= threshold:
                    filtered[ng_type][pl[i]] = phrases[pl[i]]
        return filtered

    def _dedup_levenshtein(
        self, ngrams_dict: Dict[str, int], threshold: float = 0.85
    ) -> Dict[str, int]:
        if not ngrams_dict:
            return {}
        phrases = sorted(ngrams_dict, key=lambda x: ngrams_dict[x], reverse=True)
        deduped: Dict[str, int] = {}
        removed: Set[str] = set()
        for i, p1 in enumerate(phrases):
            if p1 in removed:
                continue
            deduped[p1] = ngrams_dict[p1]
            for j in range(i + 1, len(phrases)):
                p2 = phrases[j]
                if p2 in removed:
                    continue
                maxl = max(len(p1), len(p2))
                if maxl == 0:
                    continue
                dist = levenshtein_distance(p1, p2)
                if 1 - (dist / maxl) >= threshold:
                    removed.add(p2)
        return deduped

    # ── Public API ───────────────────────────────────────────────────────

    def get_significant_words(
        self, text: str, top_n: int = DEFAULT_TOP_N
    ) -> Tuple[Set[str], Dict[str, int]]:
        words = re.findall(r"\w+", text.lower())
        sig = [w for w in words if w not in self.stop_words and len(w) > MIN_WORD_LENGTH]
        freq = Counter(sig)
        top = freq.most_common(top_n)
        return {w for w, _ in top}, dict(top)

    def get_significant_ngrams(
        self,
        text: str,
        keyword: str,
        top_n: int = DEFAULT_TOP_N,
        bert_threshold: float = DEFAULT_BERT_THRESHOLD,
        lev_threshold: float = DEFAULT_LEVENSHTEIN_THRESHOLD,
    ) -> Tuple[List[str], Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
        lower = text.lower()
        for t in self.terms_to_exclude:
            lower = re.sub(r"\b" + re.escape(t) + r"\b", "", lower)

        words = re.findall(r"\w+", lower)
        sig = [w for w in words if w not in self.stop_words and len(w) > MIN_WORD_LENGTH]
        uni_freq = Counter(sig)

        raw_bi = [" ".join(g) for g in ngrams(sig, 2)] if len(sig) >= 2 else []
        raw_tri = [" ".join(g) for g in ngrams(sig, 3)] if len(sig) >= 3 else []

        mult = 5
        raw: Dict[str, Dict[str, int]] = {
            "unigrams": dict(uni_freq.most_common(top_n * mult)),
            "bigrams": dict(Counter(raw_bi).most_common(top_n * mult)),
            "trigrams": dict(Counter(raw_tri).most_common(top_n * mult)),
        }

        kw_emb = self._bert_embed(keyword)
        relevant = self._filter_ngrams_by_relevance(raw, kw_emb, bert_threshold) if kw_emb is not None else raw

        final: Dict[str, Dict[str, int]] = {"unigrams": {}, "bigrams": {}, "trigrams": {}}
        for ng_type, phrases in relevant.items():
            if phrases:
                deduped = self._dedup_levenshtein(phrases, lev_threshold)
                final[ng_type] = dict(
                    sorted(deduped.items(), key=lambda x: x[1], reverse=True)[:top_n]
                )

        return sig, final, final

    def calculate_semantic_scores(self, texts: List[str], keyword: str) -> List[float]:
        if not texts:
            return []
        try:
            kw_emb = self.embedding_model.encode([keyword])
            text_embs = self.embedding_model.encode(texts)
            sims = cosine_similarity(kw_emb, text_embs)[0]
            return [max(0, s) * 100 for s in sims]
        except Exception as e:
            logger.error(f"Semantic score error: {e}")
            return [0.0] * len(texts)

    def calculate_seo_weighted_score(
        self,
        keyword: str,
        title: Optional[str] = None,
        h1: Optional[str] = None,
        meta_description: Optional[str] = None,
        h2_tags: Optional[List[str]] = None,
        h3_tags: Optional[List[str]] = None,
        body_content: Optional[str] = None,
    ) -> float:
        """
        SEO-weighted semantic score.
        Weights: Title 25 %, H1 20 %, Meta 15 %, Headings 15 %, Body 25 %.
        """
        weights = {
            "title": 0.25,
            "h1": 0.20,
            "meta_description": 0.15,
            "headings": 0.15,
            "body": 0.25,
        }
        try:
            kw_emb = self.embedding_model.encode([keyword])[0]
        except Exception:
            return 0.0

        scores: Dict[str, float] = {}
        total_w = 0.0

        def _score(text: Optional[str], key: str):
            nonlocal total_w
            if text and text.strip():
                try:
                    emb = self.embedding_model.encode([text[:5000]])[0]
                    s = max(0, cosine_similarity([kw_emb], [emb])[0][0])
                    scores[key] = s
                    total_w += weights[key]
                except Exception:
                    pass

        _score(title, "title")
        _score(h1, "h1")
        _score(meta_description, "meta_description")

        headings_text: List[str] = []
        if h2_tags:
            headings_text.extend([h for h in h2_tags if h and h.strip()])
        if h3_tags:
            headings_text.extend([h for h in h3_tags if h and h.strip()])
        if headings_text:
            _score(" ".join(headings_text), "headings")

        _score(body_content, "body")

        if not scores or total_w == 0:
            return 0.0
        weighted = sum(scores[k] * (weights[k] / total_w) for k in scores)
        return min(100.0, max(0.0, weighted * 100))

    def calculate_keyword_density(self, text: str, word: str) -> float:
        total = len(text.lower().split())
        if total == 0:
            return 0.0
        return (text.lower().count(word.lower()) / total) * 100

    def extract_questions(self, text: str) -> List[str]:
        pattern = QUESTION_PATTERNS.get(self.language, QUESTION_PATTERNS["en"])
        raw = re.findall(f"[^.!?]*\\b{pattern}\\b[^.!?]*[?]", text, re.IGNORECASE)
        return [re.sub(r"\s+", " ", q.strip()) for q in raw if len(q.strip()) > 10]

    def find_similar_keywords(self, keywords: List[str]) -> Dict[str, List[str]]:
        if len(keywords) < 2:
            return {}
        try:
            embs = self.embedding_model.encode(keywords)
            sim_matrix = cosine_similarity(embs)
            groups: Dict[str, List[str]] = {}
            processed: Set[int] = set()
            for i in range(len(keywords)):
                if i in processed:
                    continue
                similar = []
                for j in range(i + 1, len(keywords)):
                    if j in processed:
                        continue
                    if sim_matrix[i, j] >= self.similarity_threshold:
                        similar.append(keywords[j])
                        processed.add(j)
                if similar:
                    groups[keywords[i]] = similar
                    processed.add(i)
            return groups
        except Exception as e:
            logger.error(f"Similar keywords error: {e}")
            return {}

    @staticmethod
    def normalize_keyword(keyword: str) -> str:
        kw = unicodedata.normalize("NFKD", keyword.lower()).encode("ASCII", "ignore").decode("utf-8")
        kw = re.sub(r"[^a-z0-9\s]", "", kw)
        return " ".join(kw.split())
