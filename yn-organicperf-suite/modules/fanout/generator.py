"""
Fanout Generator — semantic query fan-out via OpenAI.
Refactored from Fanout/fanout_generator.py (FanoutPromptGenerator class).
Tkinter GUI (FanoutApp) removed; uses shared OpenAIClient.
"""
import json
import logging
from typing import Callable, Dict, List, Optional

from core.models import FanoutFacet, FanoutResult
from core.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# System prompts (per language)
# ═══════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPTS: Dict[str, str] = {
    "fr": """Tu es un expert en Query Fan-Out (QFO) et SEO sémantique.

## OBJECTIF
Générer 3 questions PRINCIPALES en LANGAGE CONVERSATIONNEL NATUREL pour chaque mot-clé.

## FORMAT OBLIGATOIRE DES 3 QUESTIONS PRINCIPALES
1. **Question "Meilleurs"** : "Quels sont les meilleurs [mot-clé] ?"
2. **Question "Comment choisir"** : "Comment choisir [mot-clé] ?"
3. **Question informationnelle** : Une question informationnelle pertinente

## CHECKLIST
1. Analyser le mot-clé → reformuler en ≤8 mots
2. Générer les 3 questions OBLIGATOIRES dans le champ "top_3_questions"
3. Décomposer en facettes sémantiques complémentaires
4. Classer les facettes (mandatory/recommended/optional)

## FORMAT DE SORTIE JSON
{
  "topic": "<reformulation ≤8 mots>",
  "top_3_questions": ["<Q1>","<Q2>","<Q3>"],
  "mandatory_facets": [{"facet":"<thématique>","intent":"<intent>","queries":["<q1>","<q2>","<q3>"],"importance_score":5}],
  "recommended_facets": [...],
  "optional_facets": [...],
  "justification": "<phrase justifiant ce fan-out>"
}""",

    "en": """You are an expert in Query Fan-Out (QFO) and semantic SEO.

## OBJECTIVE
Generate queries in NATURAL CONVERSATIONAL LANGUAGE.

## QUERY STYLE (MANDATORY)
- "I'm looking for..." / "Which are the best..."
- "Can you compare..." / "Where can I..."

## CHECKLIST
1. Analyze keyword → reformulate in ≤8 words
2. Decompose into semantic facets (360°)
3. For each facet: intent, 3-5 CONVERSATIONAL queries
4. Classify facets (mandatory/recommended/optional)

## JSON OUTPUT FORMAT
{
  "topic": "<reformulation ≤8 words>",
  "top_3_questions": ["<Q1>","<Q2>","<Q3>"],
  "mandatory_facets": [{"facet":"<theme>","intent":"<intent>","queries":["<q1>","<q2>","<q3>"],"importance_score":5}],
  "recommended_facets": [...],
  "optional_facets": [...],
  "justification": "<sentence justifying this fan-out>"
}""",

    "es": """Eres un experto en Query Fan-Out (QFO) y SEO semántico.
Genera consultas en LENGUAJE CONVERSACIONAL NATURAL.
Formato JSON:
{"topic":"<≤8 palabras>","top_3_questions":["<Q1>","<Q2>","<Q3>"],
"mandatory_facets":[{"facet":"<tema>","intent":"<intent>","queries":[...],"importance_score":5}],
"recommended_facets":[...],"optional_facets":[...],"justification":"<frase>"}""",

    "de": """Sie sind ein Experte für Query Fan-Out (QFO) und semantisches SEO.
Queries in NATÜRLICHER KONVERSATIONSSPRACHE generieren.
JSON-Format:
{"topic":"<≤8 Wörter>","top_3_questions":["<Q1>","<Q2>","<Q3>"],
"mandatory_facets":[{"facet":"<Thema>","intent":"<intent>","queries":[...],"importance_score":5}],
"recommended_facets":[...],"optional_facets":[...],"justification":"<Satz>"}""",

    "pt": """Você é um especialista em Query Fan-Out (QFO) e SEO semântico.
Gere consultas em LINGUAGEM CONVERSACIONAL NATURAL.
Formato JSON:
{"topic":"<≤8 palavras>","top_3_questions":["<Q1>","<Q2>","<Q3>"],
"mandatory_facets":[{"facet":"<tema>","intent":"<intent>","queries":[...],"importance_score":5}],
"recommended_facets":[...],"optional_facets":[...],"justification":"<frase>"}""",
}

_USER_PROMPTS: Dict[str, str] = {
    "fr": 'Effectue un fan-out sémantique complet pour :\n\nMOT-CLÉ : "{kw}"\n\nRetourne UNIQUEMENT le JSON strict.',
    "en": 'Perform a complete semantic fan-out for:\n\nKEYWORD: "{kw}"\n\nReturn ONLY strict JSON.',
    "es": 'Realiza un fan-out semántico completo para:\n\nPALABRA CLAVE: "{kw}"\n\nDevuelve SOLO JSON estricto.',
    "de": 'Führen Sie ein vollständiges semantisches Fan-Out durch für:\n\nKEYWORD: "{kw}"\n\nGeben Sie NUR striktes JSON zurück.',
    "pt": 'Realize um fan-out semântico completo para:\n\nPALAVRA-CHAVE: "{kw}"\n\nRetorne APENAS JSON estrito.',
}


class FanoutGenerator:
    """Generates semantic fan-out queries for keywords via OpenAI."""

    def __init__(self, openai_client: Optional[OpenAIClient] = None, model: str = "gpt-4o-mini"):
        self.client = openai_client or OpenAIClient()
        self.model = model

    # ═══════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════

    def generate(self, keyword: str, language: str = "fr") -> FanoutResult:
        """Generate fan-out for a single keyword."""
        lang = language.lower()[:2]
        sys_prompt = _SYSTEM_PROMPTS.get(lang, _SYSTEM_PROMPTS["en"])
        user_prompt = _USER_PROMPTS.get(lang, _USER_PROMPTS["en"]).format(kw=keyword)

        raw = self.client.chat_json(user_prompt, system=sys_prompt, temperature=0.7, max_tokens=3000)
        if not raw:
            return self._fallback(keyword, "Empty response from OpenAI")

        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as e:
            return self._fallback(keyword, str(e))

        return self._to_model(keyword, data)

    def generate_batch(
        self,
        keywords: List[str],
        language: str = "fr",
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[FanoutResult]:
        """Generate fan-out for multiple keywords."""
        results: List[FanoutResult] = []
        for idx, kw in enumerate(keywords, 1):
            if on_progress:
                on_progress(idx, len(keywords), kw)
            results.append(self.generate(kw, language))
        return results

    @staticmethod
    def extract_top_queries(result: FanoutResult, top_n: int = 10) -> List[str]:
        """Extract top-N queries ranked by facet priority and importance."""
        scored: List[tuple] = []
        for priority, facets in ((3, result.mandatory), (2, result.recommended), (1, result.optional)):
            for f in facets:
                for q in f.queries:
                    scored.append((q, priority * f.importance_score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [q for q, _ in scored[:top_n]]

    # ═══════════════════════════════════════════════════════════════════════
    # Internals
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _to_model(keyword: str, data: Dict) -> FanoutResult:
        def _facets(key: str) -> List[FanoutFacet]:
            return [
                FanoutFacet(
                    facet=f.get("facet", ""),
                    intent=f.get("intent", ""),
                    queries=f.get("queries", []),
                    importance_score=f.get("importance_score", 1),
                    preferred_formats=f.get("preferred_formats", []),
                )
                for f in data.get(key, [])
            ]

        return FanoutResult(
            keyword=keyword,
            topic=data.get("topic", keyword),
            top_3_questions=data.get("top_3_questions", []),
            mandatory=_facets("mandatory_facets"),
            recommended=_facets("recommended_facets"),
            optional=_facets("optional_facets"),
            justification=data.get("justification", ""),
        )

    @staticmethod
    def _fallback(keyword: str, error: str) -> FanoutResult:
        return FanoutResult(
            keyword=keyword,
            topic=keyword,
            top_3_questions=[],
            mandatory=[
                FanoutFacet(
                    facet="Général",
                    intent="informational",
                    queries=[f"Qu'est-ce que {keyword}", f"Comment fonctionne {keyword}"],
                    importance_score=5,
                )
            ],
            recommended=[],
            optional=[],
            justification=f"Fallback — {error}",
            error=error,
        )
