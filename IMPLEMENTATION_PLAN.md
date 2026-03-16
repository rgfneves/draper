# Draper — Plano de Implementação
## Para execução por IA (Cascade)

> **Regra**: Cada sprint entrega algo funcional e testável.
> **Regra**: Cada arquivo criado precisa ter teste correspondente.
> **Regra**: Nenhum sprint começa sem o checklist do anterior estar 100%.

---

## Correções Identificadas no concept_v2

Antes de implementar, estas correções devem ser aplicadas:

### Correção 1: `runner.py` — AI filter deve rodar em re-scoring
**Problema**: No concept_v2, quando `score_only=True` o AI filter é pulado. Mas re-scoring deveria permitir re-avaliar o filtro IA também.
**Correção**: Separar flags `--skip-scrape` e `--skip-ai-filter` ao invés de um único `--score-only`.

### Correção 2: `apify_client.py` — `.call()` já faz polling
**Problema**: `apify_client.actor(id).call(run_input)` já aguarda o fim da execução por padrão (blocking). O polling manual que definimos no concept_v2 é redundante com `.call()`.
**Correção**: Usar `.start()` ao invés de `.call()` para execução assíncrona, e aí sim aplicar polling manual. OU manter `.call()` e remover o polling wrapper. Recomendo `.call()` com `timeout_secs` que a própria lib oferece — mais simples.

### Correção 3: Seeds separados por plataforma
**Problema**: `config/seeds.py` é flat, mas Instagram usa hashtags e TikTok usa hashtags + keywords de busca.
**Correção**: Seeds devem ser um dict `{ "instagram": { "hashtags": [...] }, "tiktok": { "hashtags": [...], "search_queries": [...] } }`.

### Correção 4: Arquivos `__init__.py` faltando
**Problema**: `config/` não tem `__init__.py` listado.
**Correção**: Todos os packages Python precisam de `__init__.py`.

### Melhoria 1: Logging estruturado
**Proposta**: Usar `logging` stdlib com formato `[%(asctime)s][%(name)s][%(levelname)s] %(message)s`. Sem dependência extra. Cada módulo cria seu logger: `logger = logging.getLogger(__name__)`.

### Melhoria 2: Dry-run mode
**Proposta**: Flag `--dry-run` que mostra o que seria feito sem chamar Apify/OpenAI. Útil para debug de seeds e filtros.

### Melhoria 3: Cost tracking real
**Proposta**: Apify retorna custo no objeto `run`. OpenAI retorna `usage.total_tokens`. Gravar ambos em `pipeline_runs` para controle real de custo por run.

---

## Sprint 0 — Scaffold e Configuração
**Duração**: ~30 min
**Objetivo**: Estrutura de pastas, dependências, config segura.

### Tarefas

1. Criar estrutura de diretórios:
```
draper/
├── config/__init__.py
├── config/settings.py
├── config/filters.py
├── config/seeds.py
├── pipeline/__init__.py
├── platforms/__init__.py
├── db/__init__.py
├── dashboard/__init__.py
├── tests/__init__.py
```

2. Criar `requirements.txt`:
```
apify-client>=1.7
openai>=1.30
pandas>=2.0
streamlit>=1.35
python-dotenv>=1.0
pytest>=8.0
```

3. Criar `.env.example` (sem valores reais):
```env
APIFY_API_TOKEN=
OPENAI_API_KEY=
GPT_NICHE_MODEL=ft:gpt-3.5-turbo-0125:worldpackers:leads-ai-wp-4:BVTeAsTC
GPT_FILTER_MODEL=gpt-4o-mini
DB_PATH=draper.db
LOG_LEVEL=INFO
```

4. Criar `.gitignore`:
```
.env
*.db
__pycache__/
*.pyc
*.csv
*.jsonl
.pytest_cache/
```

5. Criar `config/settings.py` — lê `.env`, expõe constantes.

6. Criar `config/filters.py` — thresholds por plataforma.

7. Criar `config/seeds.py` — hashtags/keywords migrados dos notebooks, separados por plataforma.

### Checklist Sprint 0
- [ ] Toda a árvore de diretórios existe com `__init__.py`
- [ ] `requirements.txt` existe e pode ser instalado (`pip install -r requirements.txt`)
- [ ] `.env.example` criado (sem segredos)
- [ ] `.gitignore` criado
- [ ] `config/settings.py` carrega `.env` e exporta constantes
- [ ] `config/filters.py` tem thresholds Instagram e TikTok
- [ ] `config/seeds.py` tem hashtags/keywords extraídos dos notebooks
- [ ] **Teste**: `python -c "from config.settings import APIFY_API_TOKEN"` funciona
- [ ] **Teste**: `pytest tests/` roda (mesmo sem testes ainda, sem erro de import)

---

## Sprint 1 — Banco de Dados
**Duração**: ~1h
**Objetivo**: Schema, models, repository CRUD. Tudo testável sem Apify/OpenAI.

### Tarefas

1. Criar `db/schema.sql` com as 5 tabelas (creators, posts, score_history, pipeline_runs, outreach).

2. Criar `db/models.py` — dataclasses Python que espelham as tabelas:
```python
@dataclass
class Creator:
    id: int | None
    platform: str
    username: str
    # ... todos os campos
```

3. Criar `db/connection.py` — abre/cria SQLite, aplica schema:
```python
def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Abre conexão e garante que schema existe."""
```

4. Criar `db/repository.py` — CRUD:
```python
# Funções obrigatórias:
def upsert_creator(conn, creator: Creator) -> int
def upsert_post(conn, post: Post) -> int
def get_creator_by_username(conn, platform, username) -> Creator | None
def get_all_creators(conn, platform=None, status=None) -> list[Creator]
def update_creator_score(conn, creator_id, scores: dict) -> None
def start_run(conn, platform, seeds) -> int
def finish_run(conn, run_id, status, stats=None) -> None
def insert_score_history(conn, creator_id, run_id, score, followers, engagement) -> None
def get_score_history(conn, creator_id) -> list[dict]
```

5. Criar `tests/test_db.py`:
```python
# Testes obrigatórios:
# - test_create_schema_on_empty_db
# - test_upsert_creator_new
# - test_upsert_creator_existing_updates
# - test_upsert_creator_unique_constraint
# - test_upsert_post_deduplication
# - test_get_all_creators_filter_by_platform
# - test_get_all_creators_filter_by_status
# - test_start_and_finish_run
# - test_score_history_tracking
# - test_get_creator_by_username_not_found
```

### Checklist Sprint 1
- [ ] `db/schema.sql` com 5 tabelas (creators, posts, score_history, pipeline_runs, outreach)
- [ ] `db/models.py` com dataclasses Creator, Post, PipelineRun, ScoreHistory, Outreach
- [ ] `db/connection.py` abre SQLite e aplica schema automaticamente
- [ ] `db/repository.py` com todos os CRUD functions listados acima
- [ ] `tests/test_db.py` com 10+ testes
- [ ] **Todos os testes passam**: `pytest tests/test_db.py -v`
- [ ] Banco criado em memória (`:memory:`) nos testes — sem arquivo residual

---

## Sprint 2 — Platform Adapters (Apify)
**Duração**: ~1.5h
**Objetivo**: Wrappers para cada plataforma que normalizam dados do Apify para nossos models.

### Tarefas

1. Criar `platforms/apify_client.py` — wrapper genérico:
```python
def run_actor(actor_id: str, run_input: dict, timeout_secs: int = 600) -> tuple[list[dict], dict]:
    """
    Executa actor Apify e retorna (items, run_metadata).
    run_metadata inclui cost_usd para tracking.
    Usa .call() com timeout (blocking).
    """
```

2. Criar `platforms/instagram.py` — funções específicas:
```python
def discover_usernames(hashtags: list[str], limit: int) -> list[str]
def scrape_profiles(usernames: list[str]) -> list[dict]
def scrape_posts(usernames: list[str], limit_per_user: int = 15) -> list[dict]
def normalize_profile(raw: dict) -> Creator
def normalize_post(raw: dict, creator_id: int) -> Post
def classify_post_type(raw: dict) -> str  # 'video' | 'image' | 'sidecar'
def calculate_engagement(post: dict, followers: int) -> float
```

3. Criar `platforms/tiktok.py` — funções específicas:
```python
def discover_usernames(hashtags: list[str], keywords: list[str], limit: int) -> list[str]
def scrape_profiles_and_videos(usernames: list[str]) -> list[dict]
def normalize_profile(raw_videos: list[dict]) -> Creator
def normalize_post(raw: dict, creator_id: int) -> Post
def calculate_engagement(post: dict) -> float
```

4. Criar `tests/test_platforms.py`:
```python
# Testes com fixtures (JSON mockado dos notebooks):
# - test_normalize_instagram_profile
# - test_normalize_instagram_video_post
# - test_normalize_instagram_image_post
# - test_normalize_instagram_sidecar_post
# - test_normalize_tiktok_profile
# - test_normalize_tiktok_post
# - test_classify_post_type_video
# - test_classify_post_type_image
# - test_classify_post_type_sidecar
# - test_engagement_video_uses_views
# - test_engagement_image_uses_followers
# - test_engagement_tiktok_uses_plays
# - test_discover_deduplicates_usernames
```

5. Criar `tests/fixtures/` com JSONs reais extraídos dos notebooks:
```
tests/fixtures/
├── instagram_profile_sample.json
├── instagram_video_post_sample.json
├── instagram_image_post_sample.json
├── instagram_sidecar_post_sample.json
├── tiktok_video_sample.json
```

### Checklist Sprint 2
- [ ] `platforms/apify_client.py` com `run_actor()` que retorna items + metadata
- [ ] `platforms/instagram.py` com 7 funções listadas
- [ ] `platforms/tiktok.py` com 5 funções listadas
- [ ] `tests/fixtures/` com 5 JSONs de exemplo
- [ ] `tests/test_platforms.py` com 13+ testes
- [ ] **Engagement de imagem/sidecar usa `(likes+comments)/followers`** (correção do bug original)
- [ ] **Engagement de vídeo usa `(likes+comments)/views`**
- [ ] **TikTok engagement usa `(likes+comments+shares)/plays`**
- [ ] **Todos os testes passam**: `pytest tests/test_platforms.py -v`
- [ ] Nenhum teste chama Apify real — tudo mockado com fixtures

---

## Sprint 3 — Analysis + Scoring
**Duração**: ~1.5h
**Objetivo**: Cálculo de métricas e EpicTripScore funcional e testado.

### Tarefas

1. Criar `pipeline/analysis.py`:
```python
def analyze_creator(creator: Creator, posts: list[Post]) -> dict:
    """
    Calcula:
    - avg_engagement (por tipo de post, ponderado)
    - posts_last_30_days (total e por tipo)
    - posting_frequency (posts/dia)
    - aging breakdown (0-30, 31-60, 61-90, >90)
    - is_active (boolean, baseado em thresholds)
    """

def is_irrelevant_by_keywords(bio: str, captions: list[str], keywords: list[str]) -> bool
```

2. Criar `pipeline/scoring.py` — as funções do concept_v2:
```python
def score_engagement(avg_engagement: float) -> float
def score_followers(count: int) -> float
def score_niche(niche_label: str, ai_pass: bool | None) -> float
def score_growth(history: list[dict]) -> float
def score_activity(posts_last_30_days: int) -> float
def compute_epic_trip_score(creator_metrics: dict) -> dict  # retorna scores individuais + total
```

3. Criar `pipeline/niche_classifier.py`:
```python
def classify_niche(captions: list[str], hashtags: list[str]) -> str
    """Chama GPT fine-tuned e retorna label do nicho."""

def is_niche_irrelevant(niche: str, excluded_keywords: list[str]) -> bool
```

4. Criar `tests/test_analysis.py`:
```python
# - test_analyze_creator_active_profile
# - test_analyze_creator_inactive_low_posts
# - test_analyze_creator_inactive_low_followers
# - test_analyze_creator_no_posts
# - test_posting_frequency_calculation
# - test_aging_breakdown_correct_buckets
# - test_is_irrelevant_bio_luxury
# - test_is_irrelevant_caption_luxury
# - test_not_irrelevant_clean_profile
```

5. Criar `tests/test_scoring.py`:
```python
# - test_score_engagement_zero
# - test_score_engagement_max
# - test_score_engagement_mid_range
# - test_score_followers_below_min
# - test_score_followers_sweet_spot_5000
# - test_score_followers_above_max
# - test_score_followers_boundary_800
# - test_score_followers_boundary_50000
# - test_score_niche_travel_keywords
# - test_score_niche_partial
# - test_score_niche_ai_fail_overrides
# - test_score_growth_no_history
# - test_score_growth_positive
# - test_score_growth_negative
# - test_score_activity_zero_posts
# - test_score_activity_max_posts
# - test_epic_trip_score_perfect_profile
# - test_epic_trip_score_worst_profile
# - test_epic_trip_score_weights_sum_to_one
```

### Checklist Sprint 3
- [ ] `pipeline/analysis.py` com `analyze_creator()` e `is_irrelevant_by_keywords()`
- [ ] `pipeline/scoring.py` com 6 funções (5 scores + compute total)
- [ ] `pipeline/niche_classifier.py` com `classify_niche()` e `is_niche_irrelevant()`
- [ ] `tests/test_analysis.py` com 9+ testes
- [ ] `tests/test_scoring.py` com 19+ testes
- [ ] **Pesos somam 1.0** (validado em teste)
- [ ] **Score retorna dict com scores individuais** (não só o total)
- [ ] **Todos os testes passam**: `pytest tests/test_analysis.py tests/test_scoring.py -v`
- [ ] Nenhum teste chama OpenAI — niche_classifier mockado nos testes de scoring

---

## Sprint 4 — Pipeline Runner (CLI)
**Duração**: ~1h
**Objetivo**: `python -m pipeline.runner` funciona end-to-end.

### Tarefas

1. Criar `pipeline/runner.py`:
```python
"""
Uso:
    python -m pipeline.runner --platform instagram --limit 200
    python -m pipeline.runner --platform tiktok --limit 100
    python -m pipeline.runner --skip-scrape          # só re-analisa do banco
    python -m pipeline.runner --skip-ai-filter       # pula filtro IA
    python -m pipeline.runner --dry-run              # mostra o que faria
"""
import argparse
import logging

def run(platform, limit, skip_scrape, skip_ai_filter, dry_run):
    """Orquestra: discovery → scraping → save DB → analysis → scoring → save scores"""
```

2. Criar `pipeline/__main__.py`:
```python
from pipeline.runner import main
main()
```

3. Criar `pipeline/discovery.py`:
```python
def discover(platform: str, limit: int) -> list[str]:
    """
    Usa Apify para encontrar usernames a partir de seeds.
    Retorna lista deduplicada.
    """
```

4. Criar `pipeline/scraping.py`:
```python
def fetch_profiles_and_posts(platform: str, usernames: list[str]) -> tuple[list[Creator], list[Post]]:
    """
    Scrapa perfis + posts via Apify.
    Retorna dados normalizados prontos para DB.
    """
```

5. Criar `tests/test_runner.py`:
```python
# - test_dry_run_no_api_calls
# - test_skip_scrape_reads_from_db
# - test_full_run_saves_to_db (integration, com mocks do Apify)
# - test_run_tracks_pipeline_run
# - test_run_handles_apify_failure_gracefully
# - test_run_handles_openai_failure_gracefully
```

### Checklist Sprint 4
- [ ] `pipeline/runner.py` com CLI args (platform, limit, skip-scrape, skip-ai-filter, dry-run)
- [ ] `pipeline/__main__.py` permite `python -m pipeline.runner`
- [ ] `pipeline/discovery.py` busca usernames
- [ ] `pipeline/scraping.py` busca perfis e posts
- [ ] Pipeline grava `pipeline_runs` no banco (start_run → finish_run)
- [ ] `--dry-run` mostra seeds, estimativa de perfis, e para
- [ ] `--skip-scrape` lê do banco sem chamar Apify
- [ ] `tests/test_runner.py` com 6+ testes
- [ ] **Todos os testes passam**: `pytest tests/test_runner.py -v`
- [ ] **Teste de integração**: `python -m pipeline.runner --platform instagram --limit 5 --dry-run` executa sem erro

---

## Sprint 5 — AI Filter
**Duração**: ~45 min
**Objetivo**: Filtro IA subjetivo (PASSA/NÃO PASSA) funcional.

### Tarefas

1. Criar `pipeline/ai_filter.py`:
```python
def evaluate_creator(bio: str, captions: list[str], hashtags: list[str], niche: str) -> tuple[bool, str]:
    """
    Chama GPT-4o-mini com prompt de autenticidade.
    Retorna (ai_pass: bool, ai_reason: str).
    """

def evaluate_batch(creators: list[dict]) -> list[dict]:
    """Aplica evaluate_creator para uma lista. Rate-limited."""
```

2. Criar `tests/test_ai_filter.py`:
```python
# - test_evaluate_returns_bool_and_reason
# - test_evaluate_handles_empty_bio
# - test_evaluate_handles_empty_captions
# - test_evaluate_batch_processes_all
# - test_evaluate_batch_handles_api_error_continues
```

### Checklist Sprint 5
- [ ] `pipeline/ai_filter.py` com `evaluate_creator()` e `evaluate_batch()`
- [ ] Prompt inclui: bio, últimas legendas, hashtags, nicho
- [ ] Resposta parseada para (bool, str) com fallback graceful
- [ ] Rate limiting entre chamadas (sleep 0.5s)
- [ ] `tests/test_ai_filter.py` com 5+ testes
- [ ] **Todos os testes passam**: `pytest tests/test_ai_filter.py -v`
- [ ] Mock do OpenAI nos testes — sem chamada real

---

## Sprint 6 — Dashboard Streamlit
**Duração**: ~2h
**Objetivo**: Painel funcional com filtros, tabela e export CSV.

### Tarefas

1. Criar `dashboard/app.py` — entry-point Streamlit:
```python
"""
Uso: streamlit run dashboard/app.py
"""
```

2. Criar `dashboard/pages/overview.py`:
- KPIs: total creators, total qualificados, score médio, último run
- Gráfico: distribuição de scores (histograma)
- Gráfico: creators por plataforma (bar chart)

3. Criar `dashboard/pages/calibration.py`:
- Slider: seguidores (min/max)
- Slider: engagement (min/max)
- Multiselect: plataforma (Instagram, TikTok)
- Checkbox: AI filter (apenas PASSA)
- Text input: prompt livre para re-avaliação IA
- Botão: "Aplicar IA" (roda ai_filter em tempo real)
- Tabela: resultados filtrados ordenados por score
- Botão: "Export CSV"

4. Criar `dashboard/pages/profiles.py`:
- Tabela completa de todos os perfis
- Busca por username
- Link direto para perfil (Instagram/TikTok)
- Detalhes expandíveis: posts, métricas, score breakdown

5. Criar `dashboard/components/filters.py`:
```python
def render_filters() -> dict:
    """Renderiza sidebar com filtros e retorna dict de filtros ativos."""
```

6. Criar `dashboard/components/export.py`:
```python
def export_csv(df: pd.DataFrame, filename: str):
    """Botão de download de CSV no Streamlit."""
```

### Checklist Sprint 6
- [ ] `dashboard/app.py` roda com `streamlit run dashboard/app.py`
- [ ] Página Overview com 2+ KPIs e 2+ gráficos
- [ ] Página Calibration com 4+ filtros interativos
- [ ] Tabela ordenada por EpicTripScore
- [ ] Export CSV funcional (download direto no browser)
- [ ] Página Profiles com busca e detalhes expandíveis
- [ ] Filtros persistem na sessão (st.session_state)
- [ ] Dashboard lê do SQLite (sem hardcoded data)
- [ ] **Teste manual**: abrir dashboard, aplicar filtros, exportar CSV

---

## Sprint 7 — Integração End-to-End + Testes Finais
**Duração**: ~1.5h
**Objetivo**: Tudo funciona junto. Rodar pipeline → ver no dashboard → exportar.

### Tarefas

1. Criar `tests/test_integration.py`:
```python
# - test_full_pipeline_instagram_e2e (mocked Apify + OpenAI)
# - test_full_pipeline_tiktok_e2e
# - test_pipeline_result_visible_in_db
# - test_rescore_without_rescrape
# - test_deduplication_same_username_different_runs
# - test_score_history_accumulates_across_runs
```

2. Criar `README.md`:
```markdown
# Draper — Influencer Radar Platform

## Quick Start
1. cp .env.example .env  # preencher credenciais
2. pip install -r requirements.txt
3. python -m pipeline.runner --platform instagram --limit 50
4. streamlit run dashboard/app.py

## CLI Commands
...

## Architecture
...
```

3. Revisar todos os testes e garantir cobertura:
```bash
pytest tests/ -v --tb=short
```

4. Mover notebooks existentes para `notebooks/`:
```
notebooks/
├── instagram_lead_generator.ipynb
└── tiktok_lead_generator.ipynb
```

### Checklist Sprint 7
- [ ] `tests/test_integration.py` com 6+ testes
- [ ] `README.md` completo com Quick Start e CLI docs
- [ ] **TODOS os testes passam**: `pytest tests/ -v`
- [ ] **Contagem mínima de testes**: 68+ (10 db + 13 platforms + 9 analysis + 19 scoring + 6 runner + 5 ai_filter + 6 integration)
- [ ] Notebooks movidos para `notebooks/`
- [ ] `python -m pipeline.runner --platform instagram --limit 5` funciona end-to-end
- [ ] `streamlit run dashboard/app.py` mostra dados reais
- [ ] Nenhuma API key hardcoded em nenhum arquivo `.py`
- [ ] `.env.example` documentado
- [ ] `.gitignore` cobre `.env`, `*.db`, `*.csv`, `__pycache__`

---

## Sprint 8 (Opcional) — Histórico + Experimentos
**Duração**: ~1h
**Objetivo**: Score history tracking e página de experimentos.

### Tarefas

1. Implementar score_history gravação automática a cada run
2. Criar `dashboard/pages/experiments.py`:
   - Split train/val/test
   - Ajuste visual de pesos
   - Comparar scores entre versões
3. Gráfico de evolução de score por creator ao longo do tempo

### Checklist Sprint 8
- [ ] `score_history` preenchido automaticamente a cada run
- [ ] Página Experiments funcional no Streamlit
- [ ] Gráfico de evolução de score por creator
- [ ] `tests/test_experiments.py` com 3+ testes
- [ ] **Todos os testes passam**

---

## Resumo de Entregáveis por Sprint

| Sprint | Arquivos Criados | Testes | Entregável Funcional |
|--------|-----------------|--------|---------------------|
| **0** | 8 config files | 0 (import check) | Estrutura + dependências |
| **1** | 4 db files | 10+ | CRUD no SQLite funcional |
| **2** | 4 platform files + 5 fixtures | 13+ | Normalização de dados Apify |
| **3** | 3 pipeline files | 28+ | Métricas + EpicTripScore |
| **4** | 4 runner files | 6+ | CLI funcional end-to-end |
| **5** | 1 ai_filter file | 5+ | Filtro IA subjetivo |
| **6** | 6 dashboard files | manual | Painel Streamlit |
| **7** | 2 files (integration + README) | 6+ | Sistema completo |
| **Total** | **~32 arquivos** | **68+ testes** | **Plataforma funcional** |

---

## Ordem de Execução para IA

```
Sprint 0 → Sprint 1 → Sprint 2 → Sprint 3 → Sprint 4 → Sprint 5 → Sprint 6 → Sprint 7
                                                                                    ↓
                                                                              Sprint 8 (opcional)
```

**Cada sprint é independente mas sequencial.** O executor IA deve:
1. Ler o checklist do sprint
2. Implementar cada tarefa
3. Rodar os testes
4. Só avançar quando checklist está 100% ✅

---

## Custos Estimados por Run (200 perfis)

| Recurso | Custo Estimado |
|---|---|
| Apify (hashtag scraping) | ~$1.50 |
| Apify (profile scraping) | ~$2.00 |
| Apify (posts scraping) | ~$3.00 |
| OpenAI niche classification (~150 calls) | ~$0.15 |
| OpenAI AI filter (~150 calls) | ~$0.30 |
| **Total por run** | **~$7.00** |
| **Custo por lead qualificado** (est. 50 leads) | **~$0.14** |
