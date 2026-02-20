"""
EEAT Score Calculator — computes aggregate scores and improvement areas.
Refactored from Scoring/content-analyzer/core/score.py
"""
import re
import logging
from typing import Dict, List, Optional

from config.settings import EEAT_WEIGHTS

logger = logging.getLogger(__name__)


class ScoreCalculator:
    """Computes EEAT global score, entity analysis, and improvement tips."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or EEAT_WEIGHTS
        self.thresholds = {"critical": 40, "major": 60, "minor": 75, "excellent": 90}

    # ═══════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════

    def analyze_scores(self, data: Dict) -> Dict:
        """Full score analysis pipeline."""
        out = data.copy()
        entity = self._extract_entity(data)
        out["entity_analysis"] = entity
        out.update(self._content_metrics(data))
        bd = data.get("eeat_breakdown", {})
        if bd:
            out.update(self._eeat_global(bd, entity))
        lis = data.get("lisibilite_score", 0)
        if isinstance(lis, (int, float)):
            out["lisibilite_label_calculated"] = "facile" if lis >= 70 else ("moyen" if lis >= 50 else "difficile")
        out["composite_score"] = self._composite(data)
        if bd:
            out["improvement_areas"] = self._improvements(bd, entity)
            out["improvement_summary"] = self._summary(out["improvement_areas"], entity.get("main_entity", ""))
        out["quality_indicators"] = self._quality(data, out, entity)
        inds = out["quality_indicators"]
        out["compliance_score"] = int(sum(inds.values()) / max(len(inds), 1) * 100)
        out["content_structure"] = self._structure(data, entity)
        return out

    # ═══════════════════════════════════════════════════════════════════════
    # EEAT global
    # ═══════════════════════════════════════════════════════════════════════

    def _eeat_global(self, bd: Dict, entity: Dict) -> Dict:
        n = {k: self._norm(v) for k, v in bd.items()}
        expertise = n.get("info_originale", 0) * 0.4 + n.get("analyse_pertinente", 0) * 0.35 + n.get("valeur_originale", 0) * 0.25
        experience = n.get("description_complete", 0) * 0.5 + n.get("attention_lecteur", 0) * 0.5
        authority = n.get("credibilite", 0) * 0.6 + n.get("qualite_production", 0) * 0.4
        trust = n.get("titre_descriptif", 0) * 0.3 + n.get("titre_sobre", 0) * 0.3 + n.get("credibilite", 0) * 0.4

        bonus = 0
        dist = entity.get("entity_distribution", {})
        if all(dist.get(k, 0) > 0 for k in ("introduction", "body", "conclusion")):
            bonus = min(5, entity.get("entity_coverage_score", 0) / 20)

        g = (
            expertise * self.weights.get("expertise", 0.25)
            + experience * self.weights.get("experience", 0.20)
            + authority * self.weights.get("authoritativeness", 0.25)
            + trust * self.weights.get("trustworthiness", 0.15)
            + n.get("description_complete", 0) * self.weights.get("completude", 0.10)
            + n.get("attention_lecteur", 0) * self.weights.get("engagement", 0.05)
        ) + bonus

        return {
            "eeat_global_calculated": self._norm(g),
            "eeat_components": {
                "expertise": self._norm(expertise), "experience": self._norm(experience),
                "authoritativeness": self._norm(authority), "trustworthiness": self._norm(trust),
                "completude": n.get("description_complete", 0), "engagement": n.get("attention_lecteur", 0),
            },
            "eeat_quality_level": "excellent" if g >= 80 else ("good" if g >= 60 else ("average" if g >= 40 else "poor")),
            "eeat_normalized": n,
            "entity_bonus_applied": bonus,
        }

    # ═══════════════════════════════════════════════════════════════════════
    # Entity extraction
    # ═══════════════════════════════════════════════════════════════════════

    def _extract_entity(self, data: Dict) -> Dict:
        title = data.get("title_cleaned", "")
        content = data.get("content_cleaned", "")
        stops = {
            "le", "la", "les", "de", "du", "des", "à", "au", "aux", "et", "ou", "un", "une",
            "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "is", "are",
            "guide", "complet", "complete", "tout", "tous", "comment", "pourquoi", "best", "top",
        }
        # capitalized sequences in title
        seqs, cur = [], []
        for w in title.split():
            wc = w.strip(":,;.!?")
            if wc and wc[0].isupper() and wc.lower() not in stops:
                cur.append(wc)
            else:
                if cur:
                    seqs.append(" ".join(cur))
                cur = []
        if cur:
            seqs.append(" ".join(cur))

        best, best_cnt = None, 0
        for s in seqs:
            c = content.lower().count(s.lower())
            if c > best_cnt:
                best, best_cnt = s, c

        if not best or best_cnt < 2:
            words = re.findall(r"\b[A-Z][a-zà-ÿ]+\b", content)
            freq = {}
            for w in words:
                if w.lower() not in stops and len(w) > 3:
                    freq[w] = freq.get(w, 0) + 1
            if freq:
                best = max(freq, key=freq.get)
                best_cnt = freq[best]

        if not best:
            sig = [w.strip(":,;.!?") for w in title.split() if w.strip(":,;.!?").lower() not in stops]
            best = " ".join(sig[:3]) if sig else title[:50]

        mentions = content.lower().count(best.lower()) if best else 0
        parts = self._split_parts(content)
        dist = {k: v.lower().count(best.lower()) for k, v in parts.items()} if best else {}
        wc = len(content) / 5 if content else 1
        density = (mentions / wc) * 100 if wc else 0
        cov = 100 if 1 <= density <= 3 else (int(density * 100) if density < 1 else max(0, 100 - int((density - 3) * 10)))

        return {
            "main_entity": best or "",
            "entity_mentions_total": mentions,
            "entity_distribution": dist,
            "entity_in_title": (best or "").lower() in title.lower(),
            "entity_coverage_score": cov,
        }

    @staticmethod
    def _split_parts(content: str) -> Dict[str, str]:
        ps = content.split("\n\n")
        n = len(ps)
        if n <= 3:
            return {"introduction": ps[0] if ps else "", "body": " ".join(ps[1:]) if n > 1 else "", "conclusion": ps[-1] if n > 2 else ""}
        t = max(1, n // 3)
        return {"introduction": " ".join(ps[:t]), "body": " ".join(ps[t:-t]), "conclusion": " ".join(ps[-t:])}

    # ═══════════════════════════════════════════════════════════════════════
    # Improvements
    # ═══════════════════════════════════════════════════════════════════════

    def _improvements(self, bd: Dict, entity: Dict) -> List[Dict]:
        n = {k: self._norm(v) for k, v in bd.items()}
        ent = entity.get("main_entity", "le sujet")
        items = []
        cfg = self._improvement_cfg(ent)
        for key, sc in n.items():
            if key not in cfg:
                continue
            c = cfg[key]
            if sc < self.thresholds["critical"]:
                prio, recs = "critical", c.get("critical", [])
            elif sc < self.thresholds["major"]:
                prio, recs = "major", c.get("major", [])
            elif sc < self.thresholds["minor"]:
                prio, recs = "minor", c.get("minor", [])
            else:
                continue
            items.append({"area": c["area"], "metric": key, "score": sc, "priority": prio, "recommendations": recs, "impact": int((100 - sc) * c.get("w", 0.5))})

        # entity-specific
        if entity:
            items.extend(self._entity_tips(entity, ent))
        items.sort(key=lambda x: ({"critical": 0, "major": 1, "minor": 2}.get(x["priority"], 3), -x.get("impact", 0)))
        return items

    @staticmethod
    def _improvement_cfg(e: str) -> Dict:
        return {
            "info_originale": {"area": "Originalité", "w": 1.0,
                "critical": [f"🔴 Ajouter des informations uniques sur {e}"], "major": [f"🟠 Enrichir avec des perspectives uniques sur {e}"], "minor": [f"🟡 Renforcer l'originalité sur {e}"]},
            "description_complete": {"area": "Complétude", "w": 0.85,
                "critical": [f"🔴 Couvrir toutes les facettes de {e}"], "major": [f"🟠 Approfondir la description de {e}"], "minor": [f"🟡 Compléter certains aspects de {e}"]},
            "analyse_pertinente": {"area": "Pertinence", "w": 0.9,
                "critical": [f"🔴 Analyse de {e} trop superficielle"], "major": [f"🟠 Renforcer l'analyse critique de {e}"], "minor": [f"🟡 Affiner l'analyse de {e}"]},
            "valeur_originale": {"area": "Valeur ajoutée", "w": 0.95,
                "critical": [f"🔴 Aucune valeur unique sur {e}"], "major": [f"🟠 Créer une valeur distinctive pour {e}"], "minor": [f"🟡 Augmenter la valeur perçue sur {e}"]},
            "titre_descriptif": {"area": "Clarté du titre", "w": 0.6,
                "critical": [f"🔴 Titre ne décrit pas {e}"], "major": [f"🟠 Améliorer la clarté du titre"], "minor": [f"🟡 Affiner le titre"]},
            "titre_sobre": {"area": "Sobriété du titre", "w": 0.5,
                "critical": [f"🔴 Titre clickbait pour {e}"], "major": [f"🟠 Rendre le titre plus sobre"], "minor": [f"🟡 Ajuster le ton"]},
            "credibilite": {"area": "Crédibilité", "w": 0.9,
                "critical": [f"🔴 Absence de sources sur {e}"], "major": [f"🟠 Ajouter des sources fiables"], "minor": [f"🟡 Renforcer les éléments de confiance"]},
            "qualite_production": {"area": "Qualité rédactionnelle", "w": 0.7,
                "critical": [f"🔴 Nombreuses erreurs dans le contenu sur {e}"], "major": [f"🟠 Améliorer la qualité rédactionnelle"], "minor": [f"🟡 Peaufiner la rédaction"]},
            "attention_lecteur": {"area": "Engagement", "w": 0.75,
                "critical": [f"🔴 Contenu fade sur {e}"], "major": [f"🟠 Rendre le contenu plus engageant"], "minor": [f"🟡 Dynamiser le contenu"]},
        }

    @staticmethod
    def _entity_tips(entity: Dict, name: str) -> List[Dict]:
        tips = []
        if not entity.get("entity_in_title"):
            tips.append({"area": "Entité dans le titre", "metric": "entity_title", "score": 0, "priority": "major",
                         "recommendations": [f"🟠 Inclure '{name}' dans le titre"], "impact": 85})
        cov = entity.get("entity_coverage_score", 0)
        if cov < 40:
            tips.append({"area": "Couverture entité", "metric": "entity_coverage", "score": cov, "priority": "critical",
                         "recommendations": [f"🔴 '{name}' est sous-mentionné"], "impact": 95})
        elif cov < 70:
            tips.append({"area": "Couverture entité", "metric": "entity_coverage", "score": cov, "priority": "major",
                         "recommendations": [f"🟠 Augmenter les mentions de '{name}'"], "impact": 70})
        dist = entity.get("entity_distribution", {})
        missing = [k for k in ("introduction", "body", "conclusion") if dist.get(k, 0) == 0]
        if missing:
            tips.append({"area": "Distribution entité", "metric": "entity_dist", "score": 30, "priority": "major",
                         "recommendations": [f"🟠 '{name}' absent de: {', '.join(missing)}"], "impact": 80})
        return tips

    def _summary(self, items: List[Dict], entity: str) -> Dict:
        crit = [i for i in items if i["priority"] == "critical"]
        maj = [i for i in items if i["priority"] == "major"]
        if crit:
            status, msg = "critical", f"⚠️ {len(crit)} problème(s) critique(s) pour {entity}"
        elif maj:
            status, msg = "needs_improvement", f"📊 {len(maj)} amélioration(s) majeure(s) pour {entity}"
        else:
            status, msg = "good", f"✅ Bon contenu sur {entity}"
        return {
            "status": status, "message": msg,
            "critical_count": len(crit), "major_count": len(maj),
            "total_improvements": len(items),
            "top_priorities": [{"area": i["area"], "priority": i["priority"], "main_action": (i["recommendations"] or [""])[0]} for i in items[:3]],
        }

    # ═══════════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _norm(v, lo=0, hi=100) -> int:
        try:
            return max(lo, min(hi, int(round(float(v)))))
        except (ValueError, TypeError):
            return lo

    @staticmethod
    def _content_metrics(data: Dict) -> Dict:
        c = data.get("content_cleaned", "")
        t = data.get("title_cleaned", "")
        cw = len(c.split()) if c else 0
        return {
            "content_length": len(c), "content_words": cw,
            "title_length": len(t), "title_words": len(t.split()) if t else 0,
            "avg_word_length": len(c) / cw if cw else 0,
            "title_appropriate_length": 10 <= len(t) <= 60,
            "content_sufficient": len(c) >= 300,
        }

    @staticmethod
    def _composite(data: Dict) -> int:
        e = max(0, min(100, data.get("eeat_global", 0)))
        l = max(0, min(100, data.get("lisibilite_score", 0)))
        s = {"positive": 75, "neutral": 50, "negative": 25}.get(str(data.get("sentiment", "neutral")).lower(), 50)
        return int(round(e * 0.7 + l * 0.2 + s * 0.1))

    @staticmethod
    def _quality(data: Dict, out: Dict, entity: Dict) -> Dict:
        return {
            "high_eeat": out.get("eeat_global", 0) >= 60,
            "good_readability": data.get("lisibilite_score", 0) >= 60,
            "positive_sentiment": str(data.get("sentiment", "")).lower() == "positive",
            "sufficient_content": out.get("content_sufficient", False),
            "appropriate_title": out.get("title_appropriate_length", False),
            "entity_in_title": entity.get("entity_in_title", False),
            "good_entity_coverage": entity.get("entity_coverage_score", 0) >= 70,
        }

    @staticmethod
    def _structure(data: Dict, entity: Dict) -> Dict:
        c = data.get("content_cleaned", "")
        ent = entity.get("main_entity", "")
        ps = [p for p in c.split("\n\n") if len(p.strip()) > 50]
        pc = len(ps)
        we = sum(1 for p in ps if ent.lower() in p.lower()) if ent else 0
        ratio = we / pc if pc else 0
        has_h = bool(re.search(r"(?:^|\n)#{1,6}\s+\w", c, re.MULTILINE))
        has_l = bool(re.search(r"(?:^|\n)[*\-•]\s+\w", c, re.MULTILINE))
        sc = (25 if has_h else 0) + (15 if has_l else 0)
        sc += 30 if 5 <= pc <= 15 else (20 if 3 <= pc <= 20 else 10 if pc > 2 else 0)
        sc += 30 if ratio >= 0.6 else (20 if ratio >= 0.4 else (10 if ratio >= 0.2 else 0))
        return {
            "has_headings": has_h, "has_lists": has_l,
            "paragraph_count": pc, "paragraphs_with_entity": we,
            "entity_paragraph_ratio": round(ratio * 100, 1),
            "structure_score": min(100, sc),
        }
