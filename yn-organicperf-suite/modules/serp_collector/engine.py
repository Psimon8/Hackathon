"""
SERP Collector — collects Google Organic, PAA, and Knowledge Graph results via DataForSEO.
Refactored from dataforseo/app.py — no Tkinter dependency.
"""

from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from core.dataforseo_client import DataForSEOClient


def collect_serp(
    keywords: List[str],
    country_code: int,
    language_code: str,
    depth: int = 10,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Collect SERP data for a list of keywords.

    Args:
        keywords: List of keywords to search.
        country_code: DataForSEO location code (e.g. 2250 for France).
        language_code: Language code (e.g. "fr").
        depth: Number of SERP results per keyword (default 10).
        on_progress: Optional callback ``(current, total, keyword)``.

    Returns:
        Tuple of (organic_results, paa_results, knowledge_graph_results).
        Each item is a list of dicts.
    """
    client = DataForSEOClient()
    return client.search_serp_sync(
        keywords=keywords,
        country_code=country_code,
        language_code=language_code,
        depth=depth,
        on_progress=on_progress,
    )


def analyze_domain_positions(organic_results: List[Dict]) -> pd.DataFrame:
    """
    Analyze average position by domain from organic results.

    Returns a DataFrame with columns:
        domain, Average Position, Appearances, Best Position, Worst Position.
    """
    if not organic_results:
        return pd.DataFrame()

    df = pd.DataFrame(organic_results)
    domain_analysis = df.groupby("domain").agg(
        {"rank": ["mean", "count", "min", "max"]}
    ).round(2)
    domain_analysis.columns = [
        "Average Position",
        "Appearances",
        "Best Position",
        "Worst Position",
    ]
    domain_analysis = domain_analysis.sort_values("Average Position")
    domain_analysis = domain_analysis.reset_index()
    return domain_analysis


def collect_serp_multi(
    keywords: List[str],
    combinations: List[Dict],
    depth: int = 10,
    on_progress: Optional[Callable[[str, int, int, str], None]] = None,
) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Collect SERP data for multiple country/language combinations.

    Args:
        keywords: Keywords to search.
        combinations: List of dicts with ``country_code``, ``language_code``, ``country``, ``language``.
        depth: Results per keyword.
        on_progress: Callback ``(combo_name, current, total, keyword)``.

    Returns:
        Dict mapping ``"Country_Language"`` → ``{organic, paa, knowledge_graph}``.
    """
    all_results: Dict[str, Dict[str, List[Dict]]] = {}

    for combo in combinations:
        combo_name = f"{combo['country']}_{combo['language']}"

        def _progress(cur: int, tot: int, kw: str, cn=combo_name):
            if on_progress:
                on_progress(cn, cur, tot, kw)

        organic, paa, kg = collect_serp(
            keywords=keywords,
            country_code=combo["country_code"],
            language_code=combo["language_code"],
            depth=depth,
            on_progress=_progress,
        )

        all_results[combo_name] = {
            "organic": organic,
            "paa": paa,
            "knowledge_graph": kg,
        }

    return all_results
