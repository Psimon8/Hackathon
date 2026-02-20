"""
Centralized configuration for yn-organicperf-suite.
Country codes, language mappings, API endpoints, and shared constants.
"""

# ─── Country / Language Mappings ─────────────────────────────────────────────

COUNTRIES = {
    "United States": 2840,
    "United Kingdom": 2826,
    "France": 2250,
    "Germany": 2276,
    "Spain": 2724,
    "Italy": 2380,
    "Canada": 2124,
    "Australia": 2036,
    "Brazil": 2076,
    "Mexico": 2484,
    "Netherlands": 2528,
    "Belgium": 2056,
    "Switzerland": 2756,
    "Japan": 2392,
    "India": 2356,
    "Singapore": 2702,
}

LANGUAGES = {
    "English": "en",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Italian": "it",
    "Portuguese": "pt",
    "Dutch": "nl",
    "Japanese": "ja",
    "Hindi": "hi",
    "Portuguese (BR)": "pt-br",
}

# Short code → DataForSEO location code (used by Score Sémantique)
COUNTRY_CODES = {
    "FR": 2250,
    "UK": 2826,
    "US": 2840,
    "BR": 2076,
    "AU": 2036,
    "DE": 2276,
    "ES": 2724,
    "IT": 2380,
    "CA": 2124,
    "NL": 2528,
    "JP": 2392,
    "IN": 2356,
    "SG": 2702,
}

# ─── DataForSEO API ─────────────────────────────────────────────────────────

DATAFORSEO_BASE_URL = "https://api.dataforseo.com/v3"
DATAFORSEO_SERP_ENDPOINT = "/serp/google/organic/live/advanced"
DATAFORSEO_ONPAGE_ENDPOINT = "/on_page/content_parsing/live"
DATAFORSEO_KEYWORDS_POST = "/keywords_data/google_ads/search_volume/task_post"
DATAFORSEO_KEYWORDS_READY = "/keywords_data/google_ads/search_volume/tasks_ready"
DATAFORSEO_KEYWORDS_GET = "/keywords_data/google_ads/search_volume/task_get"

# ─── Google Suggest ──────────────────────────────────────────────────────────

GOOGLE_SUGGEST_URL = "http://suggestqueries.google.com/complete/search"

# ─── Rate Limiting / Batch ───────────────────────────────────────────────────

MAX_KEYWORDS_PER_BATCH = 1000
RATE_LIMIT_PER_SECOND = 0.5
MAX_DAILY_REQUESTS = 10000
REQUEST_TIMEOUT = 60
SUGGEST_TIMEOUT = 10
RETRY_DELAY = 15
MAX_RETRIES = 40

# ─── Semantic Score Defaults ─────────────────────────────────────────────────

DEFAULT_BERT_THRESHOLD = 0.5
DEFAULT_LEVENSHTEIN_THRESHOLD = 0.85
DEFAULT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_TOP_N = 50
MIN_WORD_LENGTH = 2

# ─── EEAT Scoring Weights ───────────────────────────────────────────────────

EEAT_WEIGHTS = {
    "expertise": 0.25,
    "experience": 0.20,
    "authoritativeness": 0.25,
    "trustworthiness": 0.15,
    "completude": 0.10,
    "engagement": 0.05,
}

# ─── Question Patterns (for FAQ extraction) ──────────────────────────────────

QUESTION_PATTERNS = {
    "fr": r"(qui|que|quoi|quel|quelle|quels|quelles|où|comment|pourquoi|quand|combien|est-ce|qu'|qu'est-ce)",
    "en": r"(who|what|where|when|why|how|which|whose|whom)",
    "es": r"(quién|qué|dónde|cuándo|por qué|cómo|cuál)",
    "de": r"(wer|was|wo|wann|warum|wie|welcher|welche)",
    "pt": r"(quem|que|onde|quando|por que|como|qual)",
}

# ─── Excel Styling ───────────────────────────────────────────────────────────

EXCEL_STYLES = {
    "header_color": "366092",
    "header_font_color": "FFFFFF",
}
