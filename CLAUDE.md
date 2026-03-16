# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Setup (first time):**
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env  # then fill in credentials
```

**Run tests:**
```bash
./run.sh test                          # all tests
./run.sh test tests/test_scoring.py   # single file
```

**Run pipeline:**
```bash
./run.sh pipeline --platform instagram --max-scrape 20 --max-ai-filter 10
./run.sh pipeline --platform instagram --max-scrape 50 --dry-run   # cost estimate only
./run.sh pipeline --platform instagram --skip-scrape --max-ai-filter 10  # re-analyze from DB
```

**Run dashboard:**
```bash
./run.sh dashboard
```

`run.sh` is a venv wrapper — it runs commands inside `.venv` without activation. Requires Python >=3.14.

## Architecture

Draper is an influencer discovery pipeline for budget travel creators. It scrapes Instagram/TikTok via Apify, classifies and scores creators with GPT, stores results in SQLite, and surfaces them via a Streamlit dashboard.

**Pipeline flow (pipeline/):**
1. `discovery.py` — reads `search_configs` from DB, calls Apify hashtag/keyword actors
2. `scraping.py` — normalizes raw Apify JSON to `Creator`/`Post` dataclasses
3. `analysis.py` — calculates engagement, posting frequency, activity flags
4. `niche_classifier.py` — GPT fine-tuned model classifies creator niche
5. `ai_filter.py` — GPT-4o-mini evaluates authenticity (0.5s rate-limit delay)
6. `scoring.py` — computes `EpicTripScore` (5 components: engagement 30%, niche 25%, followers 20%, growth 15%, activity 10%)

Pipeline stages are skippable via CLI flags (`--skip-scrape`, `--skip-ai-filter`, `--scrape-only`, `--dry-run`).

**Key layers:**
- `config/` — env vars (`settings.py`), platform follower thresholds + keyword allow/blocklists (`filters.py`), Apify search seeds per platform (`seeds.py`)
- `db/` — SQLite with 6 tables (`schema.sql`); `models.py` has dataclasses; `repository.py` has all CRUD
- `platforms/` — Apify actor wrappers for Instagram and TikTok; each has `discover_usernames()`, `scrape_*()`, and `normalize_*()` functions
- `dashboard/` — Streamlit app; `app.py` is the entry point; pages in `dashboard/pages/`; reusable widgets in `dashboard/components/`

**DB schema tables:** `creators`, `posts`, `pipeline_runs`, `score_history`, `outreach`, `search_configs`

**Tests:** 8 test files in `tests/`, all using mocked Apify/OpenAI and in-memory SQLite. Fixtures are JSON samples in `tests/fixtures/`.

**Env vars (see `.env.example`):** `APIFY_API_TOKEN`, `OPENAI_API_KEY`, `GPT_NICHE_MODEL` (fine-tuned), `GPT_FILTER_MODEL`, `DB_PATH`, `LOG_LEVEL`
