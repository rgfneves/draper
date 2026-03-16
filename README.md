# Draper — Influencer Radar Platform

Draper is a travel influencer lead generation platform that scrapes Instagram and TikTok via Apify, scores creators with a weighted EpicTripScore, evaluates authenticity with GPT-4o-mini, and surfaces qualified leads through a Streamlit dashboard.

---

## Setup (primeira vez)

```bash
cd draper/

# 1. Criar o ambiente virtual
python3 -m venv .venv

# 2. Instalar dependências
.venv/bin/pip install -r requirements.txt

# 3. Copiar e preencher credenciais
cp .env.example .env
# editar .env com APIFY_API_TOKEN, OPENAI_API_KEY e DATABASE_URL

# 4. Subir PostgreSQL local via Docker
docker run -d \
  --name draper-postgres \
  -e POSTGRES_USER=draper \
  -e POSTGRES_PASSWORD=draper \
  -e POSTGRES_DB=draper \
  -p 5432:5432 \
  postgres:16-alpine
```

> **Importante:** `streamlit`, `python` e `pytest` ficam dentro de `.venv/bin/`.
> Nunca use `streamlit run ...` ou `python -m ...` direto — use o `run.sh`.

> O schema e as seeds são aplicados **automaticamente** na primeira conexão — não é necessário rodar nenhum SQL manualmente.

### Comandos Docker úteis

```bash
docker ps                      # verificar se o container está rodando
docker start draper-postgres   # iniciar após reboot
docker stop draper-postgres    # parar
docker logs draper-postgres    # logs do PG
```

---

## Usando o run.sh

```bash
# Dashboard
./run.sh dashboard

# Pipeline
./run.sh pipeline --platform instagram --max-scrape 20 --scrape-only
./run.sh pipeline --platform instagram --skip-scrape --max-ai-filter 10

# Testes
./run.sh test
./run.sh test tests/test_scoring.py
```

---

## CLI — Todas as flags

```
./run.sh pipeline [OPTIONS]

  --platform {instagram,tiktok}   Plataforma (default: instagram)
  --limit INT                     Máx usernames a descobrir via Apify (default: 200)
  --max-scrape INT                Máx perfis a scrapar — controla custo Apify (default: 50)
  --max-ai-filter INT             Máx chamadas ao GPT AI filter por run (default: 30)
  --scrape-only                   Só descobre + scrapa + salva no banco. Para antes da análise.
  --skip-scrape                   Pula Apify — re-analisa creators já no banco
  --skip-ai-filter                Pula o filtro GPT-4o-mini
  --dry-run                       Mostra o que faria + estimativa de custo, sem chamar nenhuma API
```

### Fluxo recomendado (etapas separadas)

```bash
# Etapa 1 — coletar dados (só Apify, sem GPT)
./run.sh pipeline --platform instagram --max-scrape 20 --scrape-only

# Etapa 2 — analisar e filtrar (só GPT + scoring, sem re-scrapar)
./run.sh pipeline --platform instagram --skip-scrape --max-ai-filter 10
```

---

## Dashboard

```bash
# Opção 1 — via run.sh
./run.sh dashboard

# Opção 2 — direto (também funciona, app.py já resolve o path)
streamlit run dashboard/app.py

# Abre em http://localhost:8501
```

Páginas disponíveis:

| Página | O que faz |
|--------|-----------|
| **Overview** | KPIs, distribuição de scores, creators por plataforma |
| **Calibration** | Filtros interativos + export CSV |
| **Profiles** | Tabela completa com detalhes por creator |
| **Search Seeds** | Configura hashtags e keywords de busca por plataforma |

---

## Search Seeds

As seeds controlam o que o pipeline busca. São editáveis pelo dashboard (página **Search Seeds**).

| Plataforma | Método | Actor Apify | Como funciona |
|------------|--------|-------------|---------------|
| Instagram | Hashtag | `apify/instagram-hashtag-scraper` | Busca posts com a hashtag, extrai autores |
| TikTok | Hashtag | `clockworks/tiktok-scraper` | Busca vídeos com a hashtag, extrai criadores |
| TikTok | Keyword Search | `clockworks/tiktok-user-search-scraper` | Busca diretamente por perfis via texto livre |

Cada seed tem um badge **🖊️ Manual** (adicionada pelo usuário) ou **🤖 AI** (gerada por IA).

---

## Variáveis de ambiente (.env)

| Variável | Descrição |
|---|---|
| `APIFY_API_TOKEN` | Token da API Apify (obrigatório) |
| `OPENAI_API_KEY` | Chave OpenAI (obrigatório para niche + AI filter) |
| `GPT_NICHE_MODEL` | Modelo fine-tuned para classificação de nicho |
| `GPT_FILTER_MODEL` | Modelo para AI filter (default: gpt-4o-mini) |
| `DATABASE_URL` | DSN PostgreSQL (default: `postgresql://draper:draper@localhost:5432/draper`) |
| `LOG_LEVEL` | Verbosidade: DEBUG, INFO, WARNING (default: INFO) |
| `RUN_PASSWORD` | Senha para executar o pipeline pelo dashboard (default: 123123) |

---

## Arquitetura

```
draper/
├── run.sh                # Entry point para todos os comandos
├── config/
│   ├── settings.py       # Carrega .env, exporta constantes
│   ├── filters.py        # Thresholds por plataforma + keywords excluídas + TRAVEL_KEYWORDS
│   └── seeds.py          # Seeds padrão (carregados no banco na primeira execução)
│
├── db/
│   ├── schema.sql        # 6 tabelas PostgreSQL: creators, posts, score_history, pipeline_runs, outreach, search_configs
│   ├── models.py         # Dataclasses Python
│   ├── connection.py     # get_connection() — PgConnection wrapper, aplica schema e seed inicial
│   └── repository.py     # CRUD completo
│
├── platforms/
│   ├── apify_client.py   # run_actor() — blocking, retorna items + metadata
│   ├── instagram.py      # Discovery + scraping Instagram
│   └── tiktok.py         # Discovery (hashtag + keyword_search) + scraping TikTok
│
├── pipeline/
│   ├── discovery.py      # Lê search_configs do banco → chama actor correto
│   ├── scraping.py       # Normaliza perfis + posts para dataclasses
│   ├── analysis.py       # Engagement, frequência, aging de posts
│   ├── scoring.py        # EpicTripScore (5 componentes, keywords injetáveis)
│   ├── niche_classifier.py  # GPT fine-tuned → label de nicho
│   ├── ai_filter.py      # GPT-4o-mini → PASSA / NÃO PASSA
│   ├── runner.py         # Orquestrador CLI
│   └── __main__.py       # python -m pipeline.runner
│
├── dashboard/
│   ├── app.py            # Entry point Streamlit
│   ├── components/
│   │   ├── filters.py    # Sidebar com filtros
│   │   └── export.py     # Botão download CSV
│   └── pages/
│       ├── overview.py
│       ├── calibration.py
│       ├── profiles.py
│       └── seeds.py      # Gerenciamento de search seeds
│
├── scripts/
│   └── migrate_sqlite_to_pg.py  # Migração one-shot de dados SQLite → PostgreSQL
└── tests/                # testes com PostgreSQL efêmero (testing.postgresql), zero chamadas reais de API
```

### EpicTripScore

| Componente | Peso | Descrição |
|---|---|---|
| Engagement | 30% | Taxa de engajamento normalizada (0–15%) |
| Niche | 25% | Match com travel keywords + AI filter |
| Followers | 20% | Bell curve centrada em 2k–10k |
| Growth | 15% | Tendência de crescimento vs 30 dias atrás |
| Activity | 10% | Posts nos últimos 30 dias |

As `TRAVEL_KEYWORDS` e `PARTIAL_KEYWORDS` são configuráveis em `config/filters.py` e injetáveis por experimento via `compute_epic_trip_score(..., travel_keywords=[...])`.

---

## Testes

```bash
./run.sh test               # todos os 70 testes
./run.sh test tests/test_scoring.py  # arquivo específico
```

Os testes usam PostgreSQL efêmero via `testing.postgresql` (sem servidor externo necessário) e mocks de Apify/OpenAI.

> **Requisito:** `testing.postgresql` está no `requirements.txt` e sobe um PG isolado por sessão de testes automaticamente.

---

## Deploy

Ver [`DEPLOY_RENDER.md`](./DEPLOY_RENDER.md) para instruções completas de deploy no Render (web service + PostgreSQL gerenciado).

---

## Migrando dados do SQLite (se aplicável)

Se você tem um `draper.db` antigo com dados, use o script de migração:

```bash
.venv/bin/python -m scripts.migrate_sqlite_to_pg --sqlite-path draper.db
```
