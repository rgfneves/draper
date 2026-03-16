# Draper — Influencer Radar Platform
## Concept v2 · Technical Architecture & Audit

---

## 1. Proposta

Draper é uma plataforma de inteligência de influenciadores para a Epic Trip / Worldpackers.

**Missão**: Descobrir, qualificar e priorizar criadores de conteúdo travel com potencial real de converter audiência em vendas — de forma automática, escalável e auditável.

**Diferencial**: Não é uma planilha. É um pipeline vivo com scoring objetivo, persistência histórica, painel de calibração e loop de feedback do time de vendas.

---

## 2. Auditoria da Solução Atual

### 2.1 O que funciona bem

| Aspecto | Avaliação |
|---|---|
| Pipeline sequencial claro | ✅ Lógico e fácil de seguir |
| Separação por tipo de post (video/image/sidecar) | ✅ Granularidade útil |
| Aging de posts (0-30, 31-60, 61-90, >90 dias) | ✅ Sinal de atividade real |
| Filtro de nicho via GPT fine-tuned | ✅ Boa ideia, modelo específico para travel |
| Filtro por palavras-chave de exclusão (luxury etc.) | ✅ Necessário e bem implementado |
| Export CSV com 40+ campos Instagram | ✅ Rico em dados |

### 2.2 Problemas Críticos

#### 🔴 Segurança — API keys hardcoded
```python
# instagram_lead_generator.ipynb, cell 0
APIFY_API_TOKEN = 
OPENAI_API_KEY = "sk-proj-pwd8avzTCbD8tKZ8AQ4fg2JcIjOZuJhBabgBJvBe1fFNQnBWYDsYwpySOEFj9..."
```
Chaves expostas em ambos os notebooks. Qualquer commit/share vaza credenciais.

#### 🔴 Stateless — sem persistência
Cada execução é independente. Não há como:
- Saber quais perfis já foram analisados (reprocessa tudo a cada run)
- Comparar evolução de métricas ao longo do tempo
- Evitar chamar a API do Apify/OpenAI para os mesmos perfis

#### 🔴 EpicTripScore não existe
O conceito define um `EpicTripScore` composto (engagement + nicho + seguidores + crescimento + storytelling), mas os notebooks apenas filtram por critérios binários (passa/não passa). Não há ranking real.

#### 🔴 Sem deduplicação entre plataformas
Um criador pode aparecer no Instagram e no TikTok. Não há merge cross-platform.

#### 🔴 Sem EpicTripScore para crescimento
O campo `crescimento de seguidores` está no conceito mas não é coletado ou calculado. Tendência de views também ausente.

#### 🟡 Engajamento de imagens/sidecars é estimado incorretamente
```python
# Estimativa de views para imagens: likes * 10 ou followers * 0.15
return max(post_data.get('likesCount', 0) * 10, followers_count * 0.15, 100)
```
Essa heurística superestima ou subestima dependendo do perfil. Para imagens, engagement rate deveria ser `(likes + comments) / followers`, não por views.

#### 🟡 `time.sleep(30)` como estratégia de polling
```python
# tiktok_lead_generator.ipynb
time.sleep(30)
# Não verifica se o job realmente terminou
```
Race condition: se o job demorar mais que 30s, os dados virão incompletos silenciosamente.

#### 🟡 TikTok coleta apenas 7 dias vs Instagram 30 dias
Inconsistência no período de análise entre plataformas.

#### 🟡 Notebooks como unidade de execução
- Impossível re-rodar apenas uma etapa (ex: só o scoring, sem re-scraping)
- Não testável de forma isolada
- Sem logging estruturado para diagnóstico

#### 🟡 Painel de calibração não existe
O conceito descreve um Streamlit com filtros + IA filter. Não implementado.

#### 🟡 Método de experimento (train/val/test) não implementado
Definido no conceito, ignorado na implementação.

### 2.3 Campos do Conceito Não Implementados

| Campo | Status |
|---|---|
| crescimento de seguidores | ❌ Não coletado |
| tendência de views | ❌ Não calculado |
| taxa de viralização | ❌ Ausente |
| país provável da audiência | ❌ Ausente |
| qualidade da audiência (bots vs real) | ❌ Ausente |
| EpicTripScore composto | ❌ Não calculado |
| Painel de calibração | ❌ Não existe |
| Banco de dados local | ❌ Stateless (só CSV) |
| Filtro de IA via prompt (subjetivo) | ❌ Não existe |

---

## 3. Melhorias Propostas

### 3.1 Engajamento por tipo de post (corrigido)

| Tipo | Fórmula correta |
|---|---|
| Vídeo/Reels | `(likes + comments) / views` |
| Imagem | `(likes + comments) / followers` |
| Sidecar | `(likes + comments) / followers` |
| TikTok | `(likes + comments + shares) / plays` |

### 3.2 EpicTripScore — Fórmula proposta

```
EpicTripScore = (
    W_engagement  * score_engagement  +   # peso: 0.30
    W_travel      * score_travel_niche +   # peso: 0.25
    W_followers   * score_followers   +   # peso: 0.20
    W_growth      * score_growth      +   # peso: 0.15
    W_activity    * score_activity         # peso: 0.10
)
```

Onde cada `score_X` é normalizado 0–1:

- **score_engagement**: min-max no range esperado (ex: 0%–15%)
- **score_travel_niche**: 1.0 se GPT retorna travel, 0.5 se parcial, 0.0 se irrelevante
- **score_followers**: curva bell centrada em 3.000–10.000 (sweet spot Epic Trip)
- **score_growth**: crescimento relativo de seguidores nos últimos 30/60/90 dias
- **score_activity**: frequência de posts normalizada (ex: 1 post/dia = 1.0)

Pesos ajustáveis por experimento.

### 3.3 Ciclo de vida de um perfil

```
DESCOBERTO → SCRAPING → ANALISADO → QUALIFICADO → CONTATADO → RESPONDEU → CONVERTEU
                                  ↘ DESCARTADO
```

Cada estado rastreável com timestamp. Permite analytics de funil.

### 3.4 Deduplicação cross-platform

Normalizar username para detectar mesmo criador em Instagram e TikTok:
- Índice de `(platform, normalized_username)` como chave única
- Se mesmo criador aparece nas duas plataformas → merge do perfil, score médio ponderado

### 3.5 Filtro de IA subjetivo (AI Pass/Fail)

Prompt para GPT-4o-mini que avalia o perfil completo:

```
Você é um especialista em marketing de viagem para a Epic Trip.
Avalie este perfil de influenciador e responda apenas: PASSA ou NÃO PASSA.

Critérios:
- Parece um viajante autêntico (não apenas influencer de lifestyle)
- Conteúdo inspira viajar de forma independente / econômica
- Não parece conta de agência ou marca

Perfil:
Bio: {bio}
Últimas legendas: {captions}
Hashtags: {hashtags}
Nicho identificado: {niche}
```

Resultado salvo como campo `ai_filter_pass` (boolean) + `ai_filter_reason` (texto).

### 3.6 Polling correto para Apify

```python
def wait_for_run(client, run_id, timeout=300, interval=10):
    start = time.time()
    while time.time() - start < timeout:
        run = client.run(run_id).get()
        if run["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            return run
        time.sleep(interval)
    raise TimeoutError(f"Apify run {run_id} timed out after {timeout}s")
```

### 3.7 Configuração via `.env`

```env
APIFY_API_TOKEN=...
OPENAI_API_KEY=...
GPT_MODEL=ft:gpt-3.5-turbo-0125:worldpackers:leads-ai-wp-4:BVTeAsTC
DB_PATH=draper.db
```

---

## 4. Arquitetura Técnica Detalhada

### 4.1 Visão Geral

```
┌─────────────────────────────────────────────────────────┐
│                    DRAPER PLATFORM                       │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
│  │Discovery │───▶│ Scraping │───▶│    Analysis      │  │
│  │ Seeds    │    │  Apify   │    │  Metrics+Score   │  │
│  └──────────┘    └──────────┘    └────────┬─────────┘  │
│                                           │             │
│  ┌────────────────────────────────────────▼──────────┐  │
│  │               SQLite / PostgreSQL                  │  │
│  │  creators · posts · scores · runs · outreach      │  │
│  └────────────────────────────────────────┬──────────┘  │
│                                           │             │
│  ┌────────────────────────────────────────▼──────────┐  │
│  │           Streamlit Dashboard                      │  │
│  │  Filters · Ranking · AI Filter · Export CSV       │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Estrutura de Pastas

```
draper/
├── .env                          # Credenciais (nunca no git)
├── .env.example                  # Template público
├── requirements.txt
├── README.md
│
├── config/
│   ├── settings.py               # Lê .env, constantes globais
│   ├── filters.py                # Thresholds Instagram/TikTok
│   └── seeds.py                  # Hashtags e keywords seed
│
├── pipeline/
│   ├── __init__.py
│   ├── discovery.py              # Etapa 1: descoberta de usernames
│   ├── scraping.py               # Etapa 2: scraping de perfis e posts
│   ├── analysis.py               # Etapa 3: cálculo de métricas
│   ├── scoring.py                # Etapa 4: EpicTripScore
│   ├── ai_filter.py              # Etapa 5: filtro IA subjetivo
│   └── runner.py                 # Orquestra as etapas, CLI entry-point
│
├── platforms/
│   ├── __init__.py
│   ├── instagram.py              # Apify actors Instagram
│   ├── tiktok.py                 # Apify actors TikTok
│   └── apify_client.py           # Wrapper com polling correto
│
├── db/
│   ├── __init__.py
│   ├── schema.sql                # DDL das tabelas
│   ├── models.py                 # Dataclasses / TypedDicts
│   └── repository.py            # CRUD (creators, posts, runs)
│
├── dashboard/
│   ├── app.py                    # Streamlit entry-point
│   ├── pages/
│   │   ├── overview.py           # KPIs gerais
│   │   ├── calibration.py        # Filtros e scoring
│   │   ├── profiles.py           # Tabela de perfis qualificados
│   │   └── experiments.py        # Train/val/test splits
│   └── components/
│       ├── filters.py            # Widgets reutilizáveis
│       └── export.py             # Download CSV
│
├── notebooks/                    # Mantidos para exploração ad-hoc
│   ├── instagram_lead_generator.ipynb
│   └── tiktok_lead_generator.ipynb
│
└── tests/
    ├── test_scoring.py
    ├── test_analysis.py
    └── test_filters.py
```

### 4.3 Schema do Banco de Dados

```sql
-- Perfis descobertos e analisados
CREATE TABLE creators (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,          -- 'instagram' | 'tiktok'
    username        TEXT NOT NULL,
    display_name    TEXT,
    bio             TEXT,
    link_in_bio     TEXT,
    followers       INTEGER,
    following       INTEGER,
    total_posts     INTEGER,
    verified        BOOLEAN,
    business_account BOOLEAN,
    location        TEXT,
    niche           TEXT,                   -- resultado GPT
    ai_filter_pass  BOOLEAN,               -- resultado filtro IA
    ai_filter_reason TEXT,
    epic_trip_score REAL,                   -- 0.0 a 1.0
    score_engagement REAL,
    score_niche     REAL,
    score_followers REAL,
    score_growth    REAL,
    score_activity  REAL,
    status          TEXT DEFAULT 'discovered', -- ciclo de vida
    first_seen_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, username)
);

-- Posts/vídeos coletados por perfil
CREATE TABLE posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id      INTEGER REFERENCES creators(id),
    platform        TEXT NOT NULL,
    post_id         TEXT,                   -- ID nativo da plataforma
    post_type       TEXT,                   -- 'video' | 'image' | 'sidecar'
    published_at    DATETIME,
    likes           INTEGER,
    comments        INTEGER,
    shares          INTEGER,
    views           INTEGER,
    engagement_rate REAL,
    caption         TEXT,
    hashtags        TEXT,                   -- JSON array
    UNIQUE(platform, post_id)
);

-- Histórico de scores (tracking de evolução)
CREATE TABLE score_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id      INTEGER REFERENCES creators(id),
    run_id          INTEGER REFERENCES pipeline_runs(id),
    epic_trip_score REAL,
    followers       INTEGER,
    avg_engagement  REAL,
    scored_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Execuções do pipeline
CREATE TABLE pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT,
    seeds_used      TEXT,                   -- JSON: hashtags/keywords
    creators_found  INTEGER,
    creators_qualified INTEGER,
    apify_cost_usd  REAL,
    openai_cost_usd REAL,
    started_at      DATETIME,
    finished_at     DATETIME,
    status          TEXT                    -- 'running'|'done'|'failed'
);

-- Outreach tracking
CREATE TABLE outreach (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id      INTEGER REFERENCES creators(id),
    contacted_at    DATETIME,
    channel         TEXT,                   -- 'instagram_dm' | 'email'
    status          TEXT,                   -- 'sent'|'replied'|'converted'
    notes           TEXT
);
```

### 4.4 Pipeline — Módulos Detalhados

#### `pipeline/runner.py` — CLI Orquestrador

```python
# Uso:
# python -m pipeline.runner --platform instagram --limit 200
# python -m pipeline.runner --platform tiktok --from-db  # re-score sem re-scrape
# python -m pipeline.runner --score-only                  # apenas recalcula scores

def run(platform, limit, from_db=False, score_only=False):
    run_id = db.start_run(platform)
    try:
        if not score_only:
            usernames = discovery.find(platform, limit)
            raw_data = scraping.fetch(platform, usernames)
            db.upsert_creators_and_posts(raw_data)
        
        creators = db.get_unscored(platform)
        scored = scoring.score_all(creators)
        
        if not score_only:
            ai_filtered = ai_filter.evaluate(scored)
            db.save_scores(ai_filtered, run_id)
        
        db.finish_run(run_id, status="done")
    except Exception as e:
        db.finish_run(run_id, status="failed", error=str(e))
        raise
```

#### `pipeline/scoring.py` — EpicTripScore

```python
WEIGHTS = {
    "engagement": 0.30,
    "niche":      0.25,
    "followers":  0.20,
    "growth":     0.15,
    "activity":   0.10,
}

def score_engagement(avg_engagement: float) -> float:
    # Normaliza 0-15% para 0-1
    return min(avg_engagement / 0.15, 1.0)

def score_followers(count: int) -> float:
    # Bell curve: pico em 5.000, cai em extremos
    # 800-2.000: crescimento linear até 0.6
    # 2.000-10.000: plateau 0.8-1.0 (sweet spot)
    # 10.000-50.000: decay até 0.4 (muito grande para micro)
    if count < 800: return 0.0
    if count <= 2000: return 0.4 + (count - 800) / 1200 * 0.4
    if count <= 10000: return 0.8 + (count - 2000) / 8000 * 0.2
    if count <= 50000: return max(0.4, 1.0 - (count - 10000) / 40000 * 0.6)
    return 0.2

def score_niche(niche_label: str, ai_pass: bool | None) -> float:
    if ai_pass is False: return 0.0
    travel_keywords = {"travel", "viagem", "mochileiro", "backpacker",
                       "van life", "solo travel", "budget travel", "nomad"}
    if any(kw in niche_label.lower() for kw in travel_keywords):
        return 1.0
    return 0.5  # nicho parcial

def score_growth(history: list[dict]) -> float:
    # Compara followers[now] vs followers[30d atrás]
    if len(history) < 2: return 0.5  # sem histórico, neutro
    oldest = history[-1]["followers"]
    newest = history[0]["followers"]
    if oldest == 0: return 0.5
    growth_rate = (newest - oldest) / oldest
    return min(max((growth_rate + 0.10) / 0.20, 0.0), 1.0)  # -10% a +10%

def score_activity(posts_last_30_days: int) -> float:
    # 4+ posts = 0.5, 8+ posts = 0.8, 15+ = 1.0
    return min(posts_last_30_days / 15.0, 1.0)

def compute_epic_trip_score(creator: dict) -> float:
    scores = {
        "engagement": score_engagement(creator["avg_engagement"]),
        "niche":      score_niche(creator["niche"], creator.get("ai_filter_pass")),
        "followers":  score_followers(creator["followers"]),
        "growth":     score_growth(creator.get("score_history", [])),
        "activity":   score_activity(creator["posts_last_30_days"]),
    }
    return sum(WEIGHTS[k] * v for k, v in scores.items())
```

#### `platforms/apify_client.py` — Polling Correto

```python
def run_and_wait(actor_id: str, run_input: dict, timeout: int = 600) -> list[dict]:
    run = client.actor(actor_id).call(run_input=run_input)
    run_id = run["id"]
    
    start = time.time()
    while True:
        status = client.run(run_id).get()["status"]
        if status == "SUCCEEDED":
            return list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run {run_id} ended with status: {status}")
        if time.time() - start > timeout:
            raise TimeoutError(f"Run {run_id} exceeded {timeout}s")
        time.sleep(10)
```

### 4.5 Dashboard Streamlit

#### Página: Calibração

```
┌──────────────────────────────────────────────────────────┐
│  CALIBRATION PANEL                                       │
├────────────────────┬─────────────────────────────────────┤
│  FILTERS           │  RESULTS (live)                     │
│                    │                                     │
│  Seguidores        │  📊 347 perfis qualificados         │
│  [800] ──── [7000] │  ⭐ Score médio: 0.68               │
│                    │                                     │
│  Engagement        │  ┌─────────────────────────────┐   │
│  [0%] ──── [20%]   │  │ username │ score │ followers │   │
│                    │  │ @user1   │ 0.91  │ 4.200     │   │
│  Plataforma        │  │ @user2   │ 0.87  │ 3.100     │   │
│  [✓] Instagram     │  │ @user3   │ 0.84  │ 5.800     │   │
│  [✓] TikTok        │  └─────────────────────────────┘   │
│                    │                                     │
│  AI Filter         │  [Export CSV]  [Export para CRM]   │
│  [✓] Apenas PASSA  │                                     │
│                    │                                     │
│  Prompt livre:     │                                     │
│  [parece viajante  │                                     │
│   autêntico...]    │                                     │
│  [Aplicar IA]      │                                     │
└────────────────────┴─────────────────────────────────────┘
```

### 4.6 Método de Experimento

```python
# db/repository.py
def split_experiment(run_id: int, train=0.6, val=0.2, test=0.2):
    """
    Divide os perfis de um run em 3 conjuntos.
    Regra: nunca otimizar pesos usando o conjunto de teste.
    """
    creators = get_all_for_run(run_id)
    random.shuffle(creators)
    n = len(creators)
    train_set = creators[:int(n*train)]
    val_set   = creators[int(n*train):int(n*(train+val))]
    test_set  = creators[int(n*(train+val)):]
    return train_set, val_set, test_set
```

Workflow de tuning:
1. Ajustar pesos do `EpicTripScore` no **train set**
2. Validar métricas no **val set**
3. Reportar performance final no **test set** (uma vez)

---

## 5. Roadmap de Implementação

### Fase 1 — Core Pipeline (Semana 1-2)
- [ ] `config/settings.py` + `.env`
- [ ] `db/schema.sql` + `db/repository.py`
- [ ] `platforms/apify_client.py` (polling correto)
- [ ] `platforms/instagram.py` + `platforms/tiktok.py`
- [ ] `pipeline/analysis.py` (métricas corrigidas)
- [ ] `pipeline/scoring.py` (EpicTripScore v1)
- [ ] `pipeline/runner.py` (CLI)
- [ ] Migração das hashtags/keywords dos notebooks

### Fase 2 — IA + Dashboard (Semana 3)
- [ ] `pipeline/ai_filter.py` (prompt + pass/fail)
- [ ] `dashboard/app.py` (Streamlit básico)
- [ ] Página de calibração com filtros
- [ ] Export CSV do dashboard

### Fase 3 — Experimento + Histórico (Semana 4)
- [ ] `score_history` table (tracking de evolução)
- [ ] Página de experimentos (train/val/test split)
- [ ] Gráficos de score distribution
- [ ] Outreach tracking básico

### Fase 4 — Escala (Futuro)
- [ ] Migrar SQLite → PostgreSQL
- [ ] Webhook Apify (ao invés de polling)
- [ ] API REST para integração com CRM
- [ ] Detecção de bots (audience quality score)
- [ ] Coleta de crescimento de seguidores (Apify histórico)

---

## 6. Stack Técnica (Final)

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Linguagem | Python 3.11+ | Já usado, ecossistema de dados |
| Scraping | Apify API | Já funciona, anti-ban gerenciado |
| Banco local | SQLite (→ PostgreSQL) | Zero config, migração simples |
| Pipeline | Módulos Python + CLI | Testável, re-executável por etapa |
| IA Scoring | GPT fine-tuned (nicho) + GPT-4o-mini (AI filter) | Específico para travel |
| Dados | pandas | Já usado, familiar |
| Dashboard | Streamlit | Rápido de iterar, adequado para equipe |
| Config | python-dotenv | Segurança mínima necessária |
| Testes | pytest | Cobertura de scoring e análise |

```
requirements.txt
────────────────
apify-client>=1.7
openai>=1.30
pandas>=2.0
streamlit>=1.35
python-dotenv>=1.0
pytest>=8.0
```

---

## 7. Decisões de Design

### Por que módulos Python ao invés de Jupyter para produção?
Notebooks são ótimos para exploração, mas impedem re-execução por etapa, testes unitários e logging estruturado. Os notebooks são mantidos em `notebooks/` para experimentação ad-hoc.

### Por que SQLite antes de PostgreSQL?
Zero configuração de servidor. Suporta facilmente 100k+ perfis. Migração futura é simples com schema versionado.

### Por que dois modelos GPT?
- Fine-tuned `gpt-3.5-turbo` para classificação de nicho: rápido, barato, específico para travel (já treinado)
- `gpt-4o-mini` para o AI filter subjetivo: melhor raciocínio sobre autenticidade do criador, custo baixo

### Por que não usar uma plataforma de influencer marketing existente?
Foco em micro-influenciadores (800–50k), nicho muito específico (travel independente/econômico), custo por lead controlado.

---

## 8. Métricas de Sucesso do Sistema

| Métrica | Meta Fase 1 |
|---|---|
| Perfis qualificados por run | ≥ 50 |
| Custo Apify por perfil qualificado | < $0.10 |
| Custo OpenAI por perfil qualificado | < $0.02 |
| Taxa de conversão outreach | Baseline na Fase 3 |
| Tempo de run completo (200 perfis) | < 30 min |
