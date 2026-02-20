"""
EEAT Analyzer — calls OpenAI for E-E-A-T evaluation.
Refactored from Scoring/content-analyzer/core/analyze.py
Uses the shared OpenAIClient from core/.
"""
import json
import logging
import os
from typing import Dict, Optional

from core.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

_FALLBACK_TEMPLATE = """You are an expert SEO and content evaluator specializing in E-E-A-T analysis. Answer STRICTLY in valid JSON format.

Target language: {{language_target}}

Analyze this page:
URL: {{url}}
Title: {{title_raw}}
Content: {{content_text}}

Return JSON with this structure:
{
  "main_entity": "Primary subject/topic",
  "title_suggested": "Natural title in {{language_target}} (<= 60 chars)",
  "eeat": 0-100,
  "eeat_breakdown": {
    "info_originale": 0-100,
    "description_complete": 0-100,
    "analyse_pertinente": 0-100,
    "valeur_originale": 0-100,
    "titre_descriptif": 0-100,
    "titre_sobre": 0-100,
    "credibilite": 0-100,
    "qualite_production": 0-100,
    "attention_lecteur": 0-100
  },
  "sentiment": "positive|neutral|negative",
  "lisibilite": {"score": 0-100, "label": "facile|moyen|difficile"},
  "categorie": "Brand|Destination|Experience|Informational|Transactional",
  "resume": "1-2 sentences in {{language_target}}",
  "notes": "3-5 specific recommendations in {{language_target}}"
}
"""


class ContentAnalyzer:
    """Sends page data to OpenAI for EEAT scoring."""

    def __init__(self, openai_client: Optional[OpenAIClient] = None, prompt_path: Optional[str] = None):
        self.client = openai_client or OpenAIClient()
        self.template = self._load_template(prompt_path)

    # ── public API ──────────────────────────────────────────────────────────

    def analyze(self, data: Dict) -> Dict:
        """Analyse *data* via OpenAI, returning enriched dict."""
        out = data.copy()
        try:
            prompt = self._format(data)
            raw = self.client.chat(
                system_prompt="You are an expert SEO analyst. Always respond with valid JSON only.",
                user_prompt=prompt,
                temperature=0.1,
                max_tokens=2000,
            )
            parsed = self._parse_json(raw) if raw else None
            if parsed:
                out.update({
                    "ai_analysis": parsed,
                    "main_entity_ai": parsed.get("main_entity", ""),
                    "title_suggested": parsed.get("title_suggested", ""),
                    "eeat_global": parsed.get("eeat", 0),
                    "eeat_breakdown": parsed.get("eeat_breakdown", {}),
                    "sentiment": parsed.get("sentiment", "neutral"),
                    "lisibilite_score": parsed.get("lisibilite", {}).get("score", 0),
                    "lisibilite_label": parsed.get("lisibilite", {}).get("label", "moyen"),
                    "categorie": parsed.get("categorie", "Informational"),
                    "resume": parsed.get("resume", ""),
                    "notes": parsed.get("notes", ""),
                    "analysis_status": "success",
                })
            else:
                out.update(self._fallback(data, "Parsing error"))
                out["analysis_status"] = "fallback"
        except Exception as e:
            logger.error("analyze %s: %s", data.get("url", "?"), e)
            out.update(self._fallback(data, str(e)))
            out["analysis_status"] = "error"
        return out

    # ── internals ───────────────────────────────────────────────────────────

    @staticmethod
    def _load_template(path: Optional[str]) -> str:
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        # try default location relative to project root
        default = os.path.join(os.path.dirname(__file__), "prompts", "evaluate.md")
        if os.path.isfile(default):
            with open(default, "r", encoding="utf-8") as f:
                return f.read()
        return _FALLBACK_TEMPLATE

    def _format(self, data: Dict) -> str:
        t = self.template
        for key, val in {
            "url": data.get("url", ""),
            "title_raw": data.get("title_cleaned", data.get("title", "")),
            "content_text": data.get("content_cleaned", data.get("content", ""))[:6000],
            "language_target": data.get("language_for_prompt", "EN"),
        }.items():
            t = t.replace("{{" + key + "}}", str(val))
        return t

    @staticmethod
    def _parse_json(raw: str) -> Optional[Dict]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start:end])
                except Exception:
                    pass
        return None

    @staticmethod
    def _fallback(data: Dict, error: str) -> Dict:
        return {
            "eeat_global": 50, "eeat_breakdown": {k: 50 for k in (
                "info_originale", "description_complete", "analyse_pertinente",
                "valeur_originale", "titre_descriptif", "titre_sobre",
                "credibilite", "qualite_production", "attention_lecteur",
            )},
            "sentiment": "neutral",
            "lisibilite_score": 50, "lisibilite_label": "moyen",
            "categorie": "Informational", "resume": "", "notes": "",
            "analysis_error": error,
        }
