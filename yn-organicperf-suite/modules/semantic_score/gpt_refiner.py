"""
GPT Refiner for Semantic Score — refines n-gram occurrences and generates SEO briefs.
Uses OpenAI GPT-4o-mini via the shared OpenAIClient.
"""

import logging
from typing import Dict, List, Optional

from core.openai_client import OpenAIClient
from core.models import IndividualURLResult

logger = logging.getLogger(__name__)


class SemanticGPTRefiner:
    """Uses GPT-4o-mini to refine n-gram analysis and generate SEO content briefs."""

    def __init__(self):
        self.client = OpenAIClient(model="gpt-4o-mini")

    # ═══════════════════════════════════════════════════════════════════════
    # 1. Refine N-grams
    # ═══════════════════════════════════════════════════════════════════════

    def refine_ngrams(
        self,
        keyword: str,
        domain_ngrams: Dict[str, Dict[str, int]],
        competitor_ngrams: Dict[str, Dict[str, int]],
        ngram_differential: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Optional[List[Dict]]:
        """
        Send raw n-gram data to GPT-4o-mini for semantic deduplication,
        noise removal, categorization, and SEO priority scoring.

        Returns a list of dicts:
        [
            {
                "ngram": str,
                "type": "unigram" | "bigram" | "trigram",
                "category": "intent" | "entity" | "modifier" | "question" | "action" | "topic",
                "priority_score": int (1-10),
                "occurrences_domain": int,
                "occurrences_competitor": float
            }, ...
        ]
        """
        # Build a compact representation of n-grams for the prompt
        ngram_data = self._build_ngram_summary(domain_ngrams, competitor_ngrams, ngram_differential)
        if not ngram_data:
            return None

        system_prompt = (
            "Tu es un expert SEO spécialisé en analyse sémantique et optimisation de contenu. "
            "Tu dois analyser des n-grams extraits des pages d'un domaine et de ses concurrents "
            "pour un mot-clé donné, puis les raffiner pour en extraire les termes les plus pertinents."
        )

        user_prompt = f"""Mot-clé principal : "{keyword}"

Voici les n-grams extraits de l'analyse sémantique (domaine vs concurrents) :

{ngram_data}

**Instructions :**
1. **Fusionne** les n-grams sémantiquement identiques ou très proches (ex: "agence seo" et "agences seo")
2. **Supprime** les n-grams non pertinents, génériques ou bruyants (ex: stop words isolés, fragments sans sens)
3. **Catégorise** chaque n-gram retenu parmi : "intent" (intention de recherche), "entity" (entité/marque/lieu), "modifier" (modificateur/qualificatif), "question" (interrogation), "action" (verbe d'action), "topic" (thématique/sujet)
4. **Attribue un score de priorité SEO** de 1 à 10 (10 = indispensable à optimiser) basé sur la pertinence pour le mot-clé, la fréquence concurrentielle, et le potentiel d'optimisation
5. Conserve les occurrences domaine et concurrent moyennes

Retourne un JSON avec la structure exacte :
{{
    "refined_ngrams": [
        {{
            "ngram": "terme ou expression",
            "type": "unigram|bigram|trigram",
            "category": "intent|entity|modifier|question|action|topic",
            "priority_score": 8,
            "occurrences_domain": 5,
            "occurrences_competitor": 3.2
        }}
    ]
}}

Retourne entre 20 et 50 n-grams maximum, triés par priority_score décroissant.
"""

        try:
            result = self.client.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=4000,
            )
            if result and "refined_ngrams" in result:
                ngrams = result["refined_ngrams"]
                # Sort by priority descending
                ngrams.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
                return ngrams
            logger.warning("GPT refine_ngrams: unexpected response format")
            return None
        except Exception as e:
            logger.error(f"GPT refine_ngrams error: {e}", exc_info=True)
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # 2. Generate SEO Brief
    # ═══════════════════════════════════════════════════════════════════════

    def generate_seo_brief(
        self,
        keyword: str,
        refined_ngrams: Optional[List[Dict]],
        competitors: List[IndividualURLResult],
    ) -> Optional[Dict]:
        """
        Generate a complete SEO content brief based on refined n-grams
        and competitor data (title, meta, H1, H2, H3, word count).

        Returns:
        {
            "title": str,
            "meta_description": str,
            "h1": str,
            "target_word_count": int,
            "sections": [
                {"level": "h2", "heading": str, "content_description": str},
                {"level": "h3", "heading": str, "content_description": str},
                ...
            ]
        }
        """
        # Build competitor summary
        comp_summary = self._build_competitor_summary(competitors)
        # Build n-gram priority list
        ngram_priorities = self._build_ngram_priority_text(refined_ngrams)

        system_prompt = (
            "Tu es un expert en rédaction SEO et en stratégie de contenu. "
            "Tu génères des briefs de contenu complets et actionnables pour des rédacteurs web, "
            "en te basant sur l'analyse concurrentielle et les n-grams prioritaires."
        )

        user_prompt = f"""Mot-clé principal : "{keyword}"

## Données concurrentes (Top résultats Google)
{comp_summary}

## N-grams prioritaires à intégrer
{ngram_priorities}

## Instructions
Génère un brief SEO complet pour la rédaction d'un contenu optimisé sur le mot-clé "{keyword}".

Le brief doit contenir :
1. **Title** : balise title optimisée SEO (50-60 caractères), intégrant le mot-clé principal
2. **Meta description** : 150-160 caractères, incitative au clic, avec le mot-clé
3. **H1** : titre principal de la page, différent du title, naturel et engageant
4. **Nombre de mots cible** : basé sur la moyenne des concurrents
5. **Structure Hn complète** : arborescence hiérarchique de sections H2 et H3, chaque section accompagnée d'une description de 2-3 phrases du contenu recommandé. Intègre les n-grams prioritaires dans les headings et descriptions.

Retourne un JSON avec cette structure exacte :
{{
    "title": "Title SEO optimisé",
    "meta_description": "Meta description incitative de 150-160 caractères",
    "h1": "Titre H1 engageant et naturel",
    "target_word_count": 1500,
    "sections": [
        {{
            "level": "h2",
            "heading": "Titre de la section H2",
            "content_description": "Description en 2-3 phrases du contenu recommandé pour cette section, incluant les termes à intégrer."
        }},
        {{
            "level": "h3",
            "heading": "Sous-titre H3",
            "content_description": "Description du contenu recommandé pour cette sous-section."
        }}
    ]
}}

Génère entre 6 et 15 sections (H2 + H3 combinés). Les H3 doivent être des sous-sections logiques des H2 qui les précèdent.
"""

        try:
            result = self.client.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.5,
                max_tokens=4000,
            )
            if result and "title" in result and "sections" in result:
                return result
            logger.warning("GPT generate_seo_brief: unexpected response format")
            return None
        except Exception as e:
            logger.error(f"GPT generate_seo_brief error: {e}", exc_info=True)
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # Private helpers
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_ngram_summary(
        domain_ngrams: Dict[str, Dict[str, int]],
        competitor_ngrams: Dict[str, Dict[str, int]],
        ngram_differential: Optional[Dict[str, Dict[str, float]]],
    ) -> str:
        """Build a compact text representation of n-gram data for the prompt."""
        lines = []
        all_types = sorted(set(list(domain_ngrams.keys()) + list(competitor_ngrams.keys())))

        for ng_type in all_types:
            dom = domain_ngrams.get(ng_type, {})
            comp = competitor_ngrams.get(ng_type, {})
            diff = (ngram_differential or {}).get(ng_type, {})
            all_terms = sorted(set(list(dom.keys()) + list(comp.keys())),
                               key=lambda t: comp.get(t, 0), reverse=True)[:40]

            if not all_terms:
                continue

            lines.append(f"\n### {ng_type.upper()}")
            lines.append("N-gram | Occ. Domaine | Occ. Concurrent (moy.) | Différence")
            lines.append("---|---|---|---")
            for term in all_terms:
                d_val = dom.get(term, 0)
                c_val = round(comp.get(term, 0), 1)
                diff_val = round(diff.get(term, d_val - c_val), 1)
                lines.append(f"{term} | {d_val} | {c_val} | {diff_val}")

        return "\n".join(lines) if lines else ""

    @staticmethod
    def _build_competitor_summary(competitors: List[IndividualURLResult]) -> str:
        """Build a text summary of competitor page elements for the prompt."""
        lines = []
        # Filter to only competitors with content, limit to top 10
        relevant = [c for c in competitors if c.body_content][:10]

        if not relevant:
            return "Aucune donnée concurrentielle disponible."

        avg_wc = sum(c.word_count for c in relevant) / len(relevant) if relevant else 0

        for i, comp in enumerate(relevant, 1):
            lines.append(f"\n**Concurrent #{i}** (pos. {comp.position}) — {comp.word_count} mots")
            if comp.title:
                lines.append(f"- Title : {comp.title}")
            if comp.meta_description:
                lines.append(f"- Meta : {comp.meta_description[:200]}")
            if comp.h1:
                lines.append(f"- H1 : {comp.h1}")
            if comp.h2_tags:
                h2_str = " | ".join(comp.h2_tags[:10])
                lines.append(f"- H2 : {h2_str}")
            if comp.h3_tags:
                h3_str = " | ".join(comp.h3_tags[:10])
                lines.append(f"- H3 : {h3_str}")

        lines.append(f"\n**Moyenne nombre de mots concurrents : {int(avg_wc)}**")
        return "\n".join(lines)

    @staticmethod
    def _build_ngram_priority_text(refined_ngrams: Optional[List[Dict]]) -> str:
        """Format refined n-grams as text for the SEO brief prompt."""
        if not refined_ngrams:
            return "Aucun n-gram raffiné disponible. Génère le brief uniquement à partir des données concurrentes."

        lines = ["Priorité | N-gram | Type | Catégorie", "---|---|---|---"]
        for ng in refined_ngrams[:30]:
            lines.append(
                f"{ng.get('priority_score', '?')}/10 | "
                f"{ng.get('ngram', '?')} | "
                f"{ng.get('type', '?')} | "
                f"{ng.get('category', '?')}"
            )
        return "\n".join(lines)
