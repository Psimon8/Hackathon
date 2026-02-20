# YN Organic-Perf Suite

Suite d'outils SEO tout-en-un avec interface **Streamlit** — regroupe 5 modules complémentaires pour l'analyse de performance organique.

## Modules

| Module | Description |
|--------|-------------|
| **SERP Collector** | Collecte les résultats organiques, PAA et Knowledge Graph via DataForSEO |
| **Semantic Score** | Analyse sémantique des Top 10 vs votre domaine (BERT + n-grams pondérés SEO) |
| **EEAT Enhancer** | Évaluation E-E-A-T + recommandations personnalisées via OpenAI (GPT-4o-mini) |
| **Fan-out** | Expansion sémantique de mots-clés en facettes via OpenAI |
| **Travel Agent** | Recherche de volumes de mots-clés par seeds + DataForSEO |
| **Pipeline complet** | Enchaîne les 5 modules en séquence |

## Installation

```bash
# 1. Cloner le repo
git clone https://github.com/votre-org/yn-organicperf-suite.git
cd yn-organicperf-suite

# 2. Créer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Télécharger les données NLTK (première fois)
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt_tab')"
```

## Configuration

Copiez `.env.example` en `.env` et renseignez vos credentials :

```dotenv
DATAFORSEO_LOGIN=votre_email@example.com
DATAFORSEO_PASSWORD=votre_mot_de_passe_api
OPENAI_API_KEY=sk-votre-cle-openai
```

Vous pouvez aussi saisir les credentials directement dans la sidebar Streamlit (override session uniquement).

## Lancement

```bash
streamlit run app.py
```

L'application s'ouvre sur `http://localhost:8501`. Utilisez la sidebar pour naviguer entre les modules.

## Structure du projet

```
yn-organicperf-suite/
├── app.py                          # Point d'entrée Streamlit
├── requirements.txt
├── .env.example
├── .gitignore
│
├── config/
│   ├── settings.py                  # Pays, langues, endpoints, constantes
│   └── seeds/                       # Fichiers de seeds par langue (JSON)
│
├── core/
│   ├── credentials.py               # Gestion credentials (.env + sidebar)
│   ├── models.py                    # Dataclasses partagées entre modules
│   ├── dataforseo_client.py         # Client API DataForSEO unifié
│   ├── openai_client.py             # Client OpenAI avec retry/backoff
│   ├── cache.py                     # Cache JSON fichier
│   └── google_suggest.py            # Google Autocomplete
│
├── modules/
│   ├── serp_collector/
│   │   └── engine.py                # Collecte SERP + analyse domaines
│   ├── semantic_score/
│   │   ├── text_analysis.py         # BERT embeddings + n-grams + scoring
│   │   └── engine.py                # Orchestrateur async
│   ├── content_scoring/
│   │   ├── fetcher.py               # Téléchargement + extraction web
│   │   ├── cleaner.py               # Nettoyage contenu
│   │   ├── language.py              # Détection de langue
│   │   ├── analyzer.py              # Analyse OpenAI (EEAT)
│   │   ├── scorer.py                # Calcul scores composites
│   │   ├── engine.py                # Orchestrateur pipeline
│   │   └── prompts/evaluate.md      # Prompt EEAT template
│   ├── fanout/
│   │   └── generator.py             # Génération fan-out OpenAI
│   └── travel_agent/
│       ├── seeds_loader.py          # Chargement seeds JSON
│       └── engine.py                # Pipeline seeds → volumes
│
├── export/
│   └── excel_exporter.py            # Export XLSX multi-tab unifié
│
└── pages/                           # Pages Streamlit (multi-page app)
    ├── 1_SERP_Collector.py
    ├── 2_Semantic_Score.py
    ├── 3_Content_Scoring.py
    ├── 4_Fanout.py
    ├── 5_Travel_Agent.py
    └── 6_Full_Pipeline.py
```

## APIs utilisées

- **[DataForSEO](https://dataforseo.com/)** — SERP Organic, OnPage Content Parsing, Keywords Search Volume
- **[OpenAI](https://openai.com/)** — GPT-4o-mini pour l'analyse EEAT et le fan-out sémantique

## Export

Tous les résultats sont exportables en **XLSX** depuis chaque page Streamlit (bouton 📥). Le pipeline complet génère un fichier unique avec un onglet par module.

## Licence

Usage interne — YN.
