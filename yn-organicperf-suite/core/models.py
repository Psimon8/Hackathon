"""
Shared data models for yn-organicperf-suite.
All modules return these normalized types.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ─── SERP Collector Models ───────────────────────────────────────────────────

@dataclass
class SERPResult:
    keyword: str = ""
    position: Optional[int] = None
    rank: Optional[int] = None
    domain: str = ""
    title: str = ""
    url: str = ""
    description: str = ""
    result_type: str = "organic"


@dataclass
class PAAResult:
    keyword: str
    question: str = ""
    domain: str = ""
    url: str = ""
    answer_title: str = ""
    answer_description: str = ""


@dataclass
class KnowledgeGraphResult:
    keyword: str
    language: str = ""
    country: str = ""
    check_url: str = ""
    knowledge_graph_url: str = ""
    title: str = ""
    subtitle: str = ""
    description: str = ""
    rank_group: Optional[int] = None
    position: Optional[str] = ""


@dataclass
class DomainAnalysis:
    domain: str = ""
    average_position: float = 0.0
    appearances: int = 0
    best_position: int = 0
    worst_position: int = 0


# ─── Semantic Score Models ───────────────────────────────────────────────────

@dataclass
class IndividualURLResult:
    url: str
    position: int
    title: Optional[str] = None
    meta_description: Optional[str] = None
    semantic_score: Optional[float] = None
    h1: Optional[str] = None
    h2_tags: List[str] = field(default_factory=list)
    h3_tags: List[str] = field(default_factory=list)
    body_content: Optional[str] = None
    word_count: int = 0
    scrape_method: Optional[str] = None


@dataclass
class SemanticScoreResult:
    keyword: str
    domain_position: Optional[int] = None
    domain_url: Optional[str] = None
    domain_score: Optional[float] = None
    domain_content: Optional[str] = None
    domain_h1: Optional[str] = None
    domain_title: Optional[str] = None
    average_score: Optional[float] = None
    average_competitor_score: Optional[float] = None
    domain_ngrams: Dict[str, Dict[str, int]] = field(default_factory=dict)
    average_competitor_ngrams: Dict[str, Dict[str, int]] = field(default_factory=dict)
    keyword_density: Optional[float] = None
    faq_questions: List[str] = field(default_factory=list)
    ngram_differential: Optional[Dict[str, Dict[str, float]]] = None
    raw_ngrams_context: Dict[str, Dict[str, int]] = field(default_factory=dict)
    top_results: List[IndividualURLResult] = field(default_factory=list)
    error: Optional[str] = None
    analysis_time: float = 0.0


# ─── Content Scoring (EEAT) Models ──────────────────────────────────────────

@dataclass
class EEATBreakdown:
    info_originale: int = 0
    description_complete: int = 0
    analyse_pertinente: int = 0
    valeur_originale: int = 0
    titre_descriptif: int = 0
    titre_sobre: int = 0
    credibilite: int = 0
    qualite_production: int = 0
    attention_lecteur: int = 0


@dataclass
class EEATResult:
    url: str
    title: str = ""
    language: str = ""
    eeat_global: int = 0
    eeat_breakdown: EEATBreakdown = field(default_factory=EEATBreakdown)
    eeat_components: Dict[str, int] = field(default_factory=dict)
    sentiment: str = "neutral"
    lisibilite_score: int = 0
    lisibilite_label: str = "moyen"
    categorie: str = ""
    resume: str = ""
    notes: str = ""
    main_entity: str = ""
    entity_mentions: int = 0
    title_suggested: str = ""
    suggestions: List[str] = field(default_factory=list)
    composite_score: int = 0
    compliance_score: int = 0
    quality_level: str = ""
    word_count: int = 0
    word_count_before: int = 0
    word_count_after: int = 0
    content_cleaned: str = ""
    meta_description: str = ""
    status: str = "success"
    error: Optional[str] = None


# ─── Fan-Out Models ─────────────────────────────────────────────────────────

@dataclass
class FanoutFacet:
    facet: str = ""
    intent: str = ""
    queries: List[str] = field(default_factory=list)
    importance_score: int = 0
    preferred_formats: List[str] = field(default_factory=list)
    verbs: List[str] = field(default_factory=list)


@dataclass
class FanoutResult:
    keyword: str
    topic: str = ""
    top_3_questions: List[str] = field(default_factory=list)
    mandatory: List[FanoutFacet] = field(default_factory=list)
    recommended: List[FanoutFacet] = field(default_factory=list)
    optional: List[FanoutFacet] = field(default_factory=list)
    justification: str = ""
    error: Optional[str] = None


# ─── Keyword Volume Models ───────────────────────────────────────────────────

@dataclass
class KeywordVolumeResult:
    keyword: str
    origin: str = "direct"  # direct / suggest
    search_volume: Optional[int] = None
    competition: Optional[float] = None
    cpc: Optional[float] = None
    monthly_searches: List[Dict] = field(default_factory=list)
