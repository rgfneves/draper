# Draper — Fluxo Principal do Pipeline

> Documento gerado a partir da análise do código em `pipeline/runner.py` e módulos associados.
> Descreve cada etapa do pipeline de descoberta de influenciadores, com inputs e outputs precisos.

---

## Visão Geral

O dashboard de execução tem **5 passos** explícitos. As etapas de Analysis e Niche Classifier são **internas** ao runner — executam automaticamente dentro do Passo 5 e não aparecem como passos separados no dashboard.

```
Seeds (DB)
    │
    ▼
[Passo 1] Seeds de busca       → seleção de seeds ativas (UI only, sem execução)
    │
    ▼
[Passo 2] Coletar Creators     → Discovery + Profile Scraping  (--profiles-only)
    │
    ▼
[Passo 3] Filtro Inicial       → preview ao vivo no dashboard, sem chamada de API
    │
    ▼
[Passo 4] Scrapar Posts        → Post Scraping do subset filtrado  (--scrape-only)
    │
    ▼
[Passo 5] AI Filter & Score    → (--skip-scrape)
             ├── [interno] Analysis        → métricas de engagement e atividade
             ├── [interno] Niche Classifier → label de nicho via GPT
             ├── [interno] AI Filter        → avaliação de autenticidade via GPT
             └── [interno] Scoring          → EpicTripScore final (0–1)
    │
    ▼
DB (creators + score_history) → Dashboard (Leads / Perfis)
```

---

## Passo 1 — Seeds de busca

**Dashboard:** seleção de seeds ativas (UI only, sem execução de código)

**O que faz:** Permite escolher quais seeds serão usadas na coleta. Não dispara nenhum processo — apenas configura parâmetros passados ao runner nos passos seguintes.

| | Detalhe |
|---|---|
| **Input** | Seeds ativas na tabela `search_configs` do DB |
| **Dados disponíveis** | `search_type` (hashtag / location / keyword_search / country_code), `value` (ex: `"mochilero"`), `tags` |
| **Modos de seleção** | Todas as ativas · Filtrar por tag · Selecionar manualmente |
| **Output** | `selected_seed_ids: list[int] | None` — repassado como `--seed-ids` nos passos seguintes |

---

## Passo 2 — Coletar Creators

**Dashboard:** botão "⬇️ Executar Coleta" → executa `--profiles-only`

**O que faz:** Roda Discovery + Profile Scraping para todos os usernames descobertos. Para **antes** de filter, posts e análise.

**Comando gerado:**
```
pipeline.runner --platform <p> --profiles-only --limit <N> [--seed-ids <ids>]
```

### 2a — Discovery (`pipeline/discovery.py`)

| | Detalhe |
|---|---|
| **Input** | `platform`, `limit`, seeds selecionadas no Passo 1 |
| **Chama** | Apify via `platforms/instagram.py` ou `platforms/tiktok.py` |
| **Output** | `list[{ username, search_type, seed_value }]` |
| **Deduplicação** | Sim — case-insensitive, cap em `limit` |

### 2b — Profile Scraping (`pipeline/scraping.py → scrape_profiles_only`)

| | Detalhe |
|---|---|
| **Input** | Lista de usernames da etapa 2a |
| **Output** | `list[Creator]` + custo Apify em USD |
| **Custo** | ~$0.0026/perfil |

**Campos populados no `Creator`:**
```
username, platform, bio, followers, following, total_posts,
is_private, business_account, email, category,
discovered_via_type, discovered_via_value
```

**Nota TikTok:** Não há endpoint de perfil direto — busca 2 vídeos (`TIKTOK_PROFILE_PEEK = 2`) só para extrair `authorMeta`.

**Persistência:** `upsert_creator()` para cada Creator. Monta mapa `username → creator_id`.

---

## Passo 3 — Filtro Inicial

**Dashboard:** preview ao vivo, sem execução de API. Critérios editáveis na UI.

**O que faz:** Simula em tempo real quantos creators do banco passariam pelo filtro com os parâmetros configurados. Os valores são repassados como flags CLI ao Passo 4.

**Não chama o runner — lê diretamente do DB.**

**Critérios configuráveis na UI:**

| Campo da UI | Flag CLI gerada | Padrão Instagram | Padrão TikTok |
|---|---|---|---|
| Followers mínimos | `--min-followers` | 800 | 2.000 |
| Followers máximos | `--max-followers` | 7.000 | 50.000 |
| Posts totais mínimos | `--min-total-posts` | 0 | 0 |
| Ratio followers/following | `--min-follower-ratio` | 0.0 | 0.0 |
| Excluir contas business | `--exclude-business` | off | off |
| Exigir email público | `--require-email` | off | off |
| Categorias excluídas *(Instagram)* | `--excluded-categories` | — | — |
| Keywords excluídas na bio | `--excluded-keywords` | `EXCLUDED_KEYWORDS` | `EXCLUDED_KEYWORDS` |

**Output da UI:** métrica "Passariam X de Y no banco" + parâmetros prontos para Passo 4.

---

## Passo 4 — Scrapar Posts

**Dashboard:** botão "📥 Scrapar Posts" → executa `--scrape-only`

**O que faz:** Roda Discovery + Profile Scraping + Initial Filter + Post Scraping. Para **antes** de Analysis, Niche e AI. Etapa mais cara.

**Comando gerado:**
```
pipeline.runner --platform <p> --scrape-only
  --max-scrape <N> --max-posts <N>
  --min-followers <N> --max-followers <N>
  [--excluded-keywords ...] [--exclude-business]
  [--min-total-posts N] [--min-follower-ratio N]
  [--require-email] [--excluded-categories ...]
  [--seed-ids ...]
```

### Post Scraping (`pipeline/scraping.py → scrape_posts_only`)

| | Detalhe |
|---|---|
| **Input** | Usernames que passaram o Filtro Inicial, cap em `max_scrape` (slider na UI, default 30) |
| **Output** | `list[Post]` + custo Apify em USD |
| **Custo** | ~$0.0023/post × `max_posts` por creator |

**Campos populados no `Post`:**
```
creator_id, platform, post_id, post_type,
published_at, engagement_rate, caption, hashtags
```

**Persistência:** `upsert_post()` para cada Post, vinculado ao `creator_id`.

---

## Passo 5 — AI Filter & Score

**Dashboard:** text area editável com o critério de avaliação + botão "🤖 Executar AI Filter"

**O único input do usuário neste passo é o texto do critério:**

| | Detalhe |
|---|---|
| **Input** | Texto livre descrevendo o perfil ideal de creator (editável na UI) |
| **Critério padrão** | Mochileiros autênticos da América Latina, viagem de baixo custo, criadores individuais (não agências) |
| **Controle de custo** | Slider "Máx. avaliações GPT" → `--max-ai-filter N` (default: 30) |
| **Output** | Creators avaliados com `ai_filter_pass`, `ai_filter_reason` e `epic_trip_score` visíveis na tabela de resultados |

---

## O que acontece internamente no Passo 5

Ao clicar em executar, o runner (`--skip-scrape`) roda 4 sub-etapas sequenciais sem interação do usuário:

**Comando gerado:**
```
pipeline.runner --platform <p> --skip-scrape
  --max-ai-filter <N>
  [--ai-criteria "texto digitado pelo usuário"]
```

### Analysis — `pipeline/analysis.py → analyze_creator()`

| | Detalhe |
|---|---|
| **Input** | `Creator` (do DB) + seus `Post[]` carregados do DB |
| **Output** | Métricas de atividade |

| Métrica calculada | Descrição |
|---|---|
| `avg_engagement` | Média de `engagement_rate` de todos os posts |
| `posts_last_30_days` | Posts nos últimos 30 dias |
| `posts_last_60_days` | Posts nos últimos 60 dias |
| `posts_last_90_days` | Posts nos últimos 90 dias |
| `posting_frequency` | Posts/dia nos últimos 90 dias |
| `aging_breakdown` | `{0_30, 31_60, 61_90, over_90}` |
| `is_active` | `True` se `posts_last_30_days >= 4` |

**Filtro de keywords nos captions:** se bio ou qualquer caption bater com `EXCLUDED_KEYWORDS` (word-boundary), creator é marcado `"excluded"` e pulado.

**Persistência:** métricas salvas no `Creator` via `upsert_creator()`.

### Niche Classifier — `pipeline/niche_classifier.py → classify_niche()`

Só roda se `creator.niche` estiver vazio.

| | Detalhe |
|---|---|
| **Input** | `captions` (últimos 10 do DB, truncados a 800 chars) + `hashtags` (últimos 10, truncados a 400 chars) |
| **Prompt GPT** | `"Classify the creator niche in 2-4 words"` |
| **Modelo** | `GPT_NICHE_MODEL` (env var) |
| **Output** | `niche: str` — ex: `"mochilero travel"`, `"budget backpacker"` |

**Pós-classificação:** se o niche bater com `EXCLUDED_KEYWORDS` → `"excluded"`. Niche vazio → `score_niche = 0.0` (sem aprovação automática).

**Persistência:** `creator.niche` salvo via `upsert_creator()`.

### AI Filter — `pipeline/ai_filter.py → evaluate_batch()`

Só roda para creators sem `ai_filter_pass` definido, não excluídos, até o cap `--max-ai-filter`.

| | Detalhe |
|---|---|
| **Input por creator** | `{ id, bio, niche, captions[:5], hashtags[:30] }` |
| **System prompt** | Critério digitado pelo usuário no Passo 5 |
| **Modelo** | `GPT_FILTER_MODEL` (env var, ex: `gpt-4o-mini`) |
| **Output por creator** | `{ ai_filter_pass: bool, ai_filter_reason: str }` |
| **Custo** | ~$0.001/creator · rate limit: 0.5s entre chamadas |

**Persistência:** `update_creator_ai_filter(id, ai_filter_pass, ai_filter_reason)`.

### Scoring — `pipeline/scoring.py → compute_epic_trip_score()`

| | Detalhe |
|---|---|
| **Input** | `{ avg_engagement, niche, ai_filter_pass, followers, score_history, posts_last_30_days }` |
| **Output** | `{ score_engagement, score_niche, score_followers, score_growth, score_activity, epic_trip_score }` |

| Dimensão | Peso | Cálculo |
|---|---|---|
| `score_engagement` | 30% | `avg_engagement / 0.15` (normalizado 0–15% → 0–1) |
| `score_niche` | 25% | `1.0` travel kw · `0.5` partial kw · `0.0` se `ai_filter_pass=False` |
| `score_followers` | 20% | Bell curve: sweet spot 2k–10k = 1.0; < 800 = 0.0; > 50k = 0.2 |
| `score_growth` | 15% | Crescimento vs histórico: [-10%, +10%] → [0, 1]; sem histórico = 0.5 |
| `score_activity` | 10% | `posts_last_30_days / 15` (0–15 posts → 0–1) |

```
epic_trip_score = 0.30×engagement + 0.25×niche + 0.20×followers + 0.15×growth + 0.10×activity
```

**Persistência:**
- `update_creator_score()` → campos de score na tabela `creators`
- `insert_score_history()` → histórico para cálculo de growth futuro

---

## Resumo: Input → Output por Passo

| Passo | Dashboard | Input do usuário | Output visível | Custo | Persiste no DB? |
|---|---|---|---|---|---|
| 1 | Seeds | Seleção de seeds ativas | `selected_seed_ids` (repassado aos próximos passos) | — | Não |
| 2 | Coletar Creators | `limit` (slider) | Creators no banco (perfis sem posts) | ~$0.0026/perfil | ✅ `creators` |
| 3 | Filtro Inicial | Thresholds editáveis na UI | Preview "X passariam de Y" | — | Não |
| 4 | Scrapar Posts | `max_scrape` + `max_posts` (sliders) | Creators com posts no banco | ~$0.0023/post | ✅ `posts` |
| 5 | AI Filter & Score | **Texto do critério de avaliação** (text area) | Tabela de resultados com `pass`, `score`, `motivo` | ~$0.001/creator | ✅ `creators` + `score_history` |

**Sub-etapas internas do Passo 5 (sem interação do usuário):**

| Sub-etapa | Input | Output | Persiste? |
|---|---|---|---|
| Analysis | `Creator` + `Post[]` do DB | `avg_engagement`, `posts_last_30_days`, `is_active`, etc. | ✅ `creators` |
| Niche Classifier | `captions` + `hashtags` do DB | `niche: str` (2–4 palavras) | ✅ `creator.niche` |
| AI Filter | `bio, niche, captions, hashtags` + critério do usuário | `ai_filter_pass`, `ai_filter_reason` | ✅ `creators` |
| Scoring | Métricas + `score_history` | `epic_trip_score` + sub-scores | ✅ `creators` + `score_history` |

---

## Flags do CLI e Pontos de Parada

| Flag | Efeito |
|---|---|
| `--profiles-only` | Para após Passo 2 (sem filter, posts, análise) |
| `--scrape-only` | Para após Passo 4 (sem análise, AI, scoring) |
| `--skip-scrape` | Pula Passos 2–4 (usa creators já no DB) — usado pelo Passo 5 |
| `--skip-ai-filter` | Pula sub-etapa 5c (AI Filter) |
| `--dry-run` | Estima custos sem fazer chamadas reais |
