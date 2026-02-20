"""
EEAT Recommendation Generator — uses GPT-4o-mini to produce personalized
E-E-A-T improvement recommendations based on page content & scores.
"""
import json
import logging
import os
from typing import Dict, List, Optional

from core.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

_PRIORITY_EMOJI = {"critical": "🔴", "major": "🟠", "minor": "🟡"}


class RecommendationGenerator:
    """Generates personalised EEAT recommendations via GPT-4o-mini."""

    def __init__(self, openai_client: Optional[OpenAIClient] = None, prompt_path: Optional[str] = None):
        self.client = openai_client or OpenAIClient(model="gpt-4o-mini")
        self.template = self._load_template(prompt_path)

    # ── public API ──────────────────────────────────────────────────────────

    def generate(self, data: Dict) -> List[Dict]:
        """Generate EEAT recommendations for a single analysed URL.

        *data* must contain keys produced by the scoring pipeline:
        url, title_cleaned, main_entity (from entity_analysis), content_cleaned,
        eeat_breakdown, eeat_components, language_for_prompt, etc.

        Returns a list of recommendation dicts with keys:
          priority, eeat_area, section, recommendation, rationale
        """
        try:
            prompt = self._format(data)
            raw = self.client.chat(
                system_prompt=(
                    "You are an expert SEO consultant. "
                    "Always respond with valid JSON only."
                ),
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=2500,
            )
            parsed = self._parse_json(raw) if raw else None
            if parsed and "recommendations" in parsed:
                recs = parsed["recommendations"]
                # Validate & normalise each recommendation
                return [self._normalise(r) for r in recs if isinstance(r, dict)]
            logger.warning("GPT recommendations: unexpected format – raw=%s", raw[:200] if raw else "None")
            return []
        except Exception as e:
            logger.error("RecommendationGenerator error for %s: %s", data.get("url", "?"), e)
            return []

    # ── formatting ──────────────────────────────────────────────────────────

    def _format(self, data: Dict) -> str:
        entity_analysis = data.get("entity_analysis", {})
        bd = data.get("eeat_breakdown", {})
        components = data.get("eeat_components", {})
        content = data.get("content_cleaned", data.get("content", ""))

        # Build weaknesses summary from breakdown scores
        weaknesses_lines = []
        thresholds = {"critical": 40, "major": 60, "minor": 75}
        metric_labels = {
            "info_originale": "Originalité de l'information",
            "description_complete": "Complétude de la description",
            "analyse_pertinente": "Pertinence de l'analyse",
            "valeur_originale": "Valeur originale",
            "titre_descriptif": "Clarté du titre",
            "titre_sobre": "Sobriété du titre",
            "credibilite": "Crédibilité",
            "qualite_production": "Qualité rédactionnelle",
            "attention_lecteur": "Engagement lecteur",
        }
        for metric, score in bd.items():
            try:
                s = int(score)
            except (ValueError, TypeError):
                continue
            label = metric_labels.get(metric, metric)
            if s < thresholds["critical"]:
                weaknesses_lines.append(f"- 🔴 CRITICAL: {label} = {s}/100")
            elif s < thresholds["major"]:
                weaknesses_lines.append(f"- 🟠 MAJOR: {label} = {s}/100")
            elif s < thresholds["minor"]:
                weaknesses_lines.append(f"- 🟡 MINOR: {label} = {s}/100")

        weaknesses_text = "\n".join(weaknesses_lines) if weaknesses_lines else "No significant weaknesses detected."

        # Entity distribution string
        dist = entity_analysis.get("entity_distribution", {})
        dist_str = ", ".join(f"{k}: {v}" for k, v in dist.items()) if dist else "N/A"

        replacements = {
            "url": data.get("url", ""),
            "title": data.get("title_cleaned", data.get("title", "")),
            "main_entity": entity_analysis.get("main_entity", data.get("main_entity_ai", "N/A")),
            "categorie": data.get("categorie", "Informational"),
            "content_extract": content[:3000] if content else "(no content)",
            "eeat_global": str(data.get("eeat_global_calculated", data.get("eeat_global", 0))),
            "expertise": str(components.get("expertise", 0)),
            "experience": str(components.get("experience", 0)),
            "authority": str(components.get("authoritativeness", 0)),
            "trust": str(components.get("trustworthiness", 0)),
            "info_originale": str(bd.get("info_originale", 0)),
            "description_complete": str(bd.get("description_complete", 0)),
            "analyse_pertinente": str(bd.get("analyse_pertinente", 0)),
            "valeur_originale": str(bd.get("valeur_originale", 0)),
            "titre_descriptif": str(bd.get("titre_descriptif", 0)),
            "titre_sobre": str(bd.get("titre_sobre", 0)),
            "credibilite": str(bd.get("credibilite", 0)),
            "qualite_production": str(bd.get("qualite_production", 0)),
            "attention_lecteur": str(bd.get("attention_lecteur", 0)),
            "weaknesses": weaknesses_text,
            "entity_in_title": str(entity_analysis.get("entity_in_title", False)),
            "entity_mentions": str(entity_analysis.get("entity_mentions_total", 0)),
            "entity_distribution": dist_str,
            "language_target": data.get("language_for_prompt", "EN"),
        }

        t = self.template
        for key, val in replacements.items():
            t = t.replace("{{" + key + "}}", val)
        return t

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _load_template(path: Optional[str]) -> str:
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        default = os.path.join(os.path.dirname(__file__), "prompts", "recommend.md")
        if os.path.isfile(default):
            with open(default, "r", encoding="utf-8") as f:
                return f.read()
        # Bare-bones fallback
        return (
            "Generate 5-8 E-E-A-T recommendations in JSON for the page at {{url}} "
            "about {{main_entity}}. Weaknesses: {{weaknesses}}. "
            "Return {\"recommendations\": [{\"priority\": \"...\", \"eeat_area\": \"...\", "
            "\"section\": \"...\", \"recommendation\": \"...\", \"rationale\": \"...\"}]}."
        )

    @staticmethod
    def _normalise(rec: Dict) -> Dict:
        """Ensure recommendation dict has all expected keys."""
        priority = rec.get("priority", "minor")
        if priority not in ("critical", "major", "minor"):
            priority = "minor"
        return {
            "priority": priority,
            "eeat_area": rec.get("eeat_area", "Content Coverage"),
            "section": rec.get("section", "overall"),
            "recommendation": rec.get("recommendation", ""),
            "rationale": rec.get("rationale", ""),
        }

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
    def format_suggestions(recommendations: List[Dict]) -> List[str]:
        """Convert structured recommendations to formatted suggestion strings."""
        lines = []
        for rec in recommendations:
            emoji = _PRIORITY_EMOJI.get(rec.get("priority", "minor"), "🟡")
            text = rec.get("recommendation", "")
            if text:
                lines.append(f"{emoji} {text}")
        return lines
