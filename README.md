# ENS491 BlueSky Project

This repository now combines **two complementary BlueSky workstreams** in a single place:

1. **Our ENS491 analysis pipeline** at the repository root  
   Focused on Turkish political discourse collection, sentiment analysis, ideology analysis, network analysis, and visual reporting.

2. **A collaborator's real-time custom feed generator** under [`bluesky_feed_generator/`](./bluesky_feed_generator)  
   Focused on live AT Protocol firehose ingestion, domain classification, stance detection, database-backed ranking, and feed serving.

The goal of this merged structure is to keep our current project files intact while also preserving the collaborator's feed-generation codebase for future integration, comparison, and deployment work.

---

## Repository Layout

### Root: Our ENS491 analysis project

Key folders and files:

- `analysis.ipynb` and `bluesky_politician_scraper.ipynb`
- `data/`
- `src/`
- `outputs/`
- `interface/`
- `run_pipeline.py`
- `requirements.txt`

This root project handles:

- account verification and handle collection
- BlueSky post fetching and weekly search
- keyword extraction
- sentiment and ideology analysis
- political network construction
- report-ready visualizations and interface outputs

### Subfolder: Collaborator feed generator

The collaborator's repository is included under:

- [`bluesky_feed_generator/`](./bluesky_feed_generator)

That project contains:

- `config/`
- `data_collection/`
- `database/`
- `feed_generator/`
- `nlp/`
- `scripts/`
- deployment files such as `Dockerfile.worker`, `Procfile`, `runtime.txt`
- dedicated requirements files (`requirements-server.txt`, `requirements-nlp.txt`)

This subproject handles:

- real-time AT Protocol firehose listening
- seed-based and keyword-based candidate filtering
- Turkish NLP embedding and domain classification
- stance detection
- database-backed ranking and custom feed serving

---

## Why the Repository Is Structured This Way

We wanted the repository to include **both our up-to-date ENS491 work** and **the collaborator's BlueSky feed-generator implementation** without destroying the structure of our current project.

For that reason:

- our current project remains at the repository root
- the collaborator code is preserved in its own dedicated subfolder
- AI helper files such as `CLAUDE.md` were intentionally removed from the final repository tree

---

## Root Project Quick Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run_pipeline.py
```

Main analysis code lives in `src/`, and generated results are written under `outputs/`.

---

## Feed Generator Quick Start

See the dedicated documentation here:

- [`bluesky_feed_generator/README.md`](./bluesky_feed_generator/README.md)

In short, that subproject is intended for:

- local firehose experiments
- Railway deployment
- custom BlueSky feed publication

---

## Notes

- The root analysis project and the feed generator are **related but not identical systems**.
- Some functionality overlaps conceptually, but the two codebases were kept separate on purpose to avoid breaking either workflow.
- If we later decide to unify them, this merged repository gives us a clean base to do that.
