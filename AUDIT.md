# Draper — Auditoria do Sistema

> Auditoria completa do fluxo, arquitetura, gaps e bugs.
> Foco principal: aba **▶️ Executar** (`dashboard/pages/run.py`).

---

## 1. Visão Geral da Arquitetura

```
Seeds (DB)
    │
    ▼
[Discovery] → Apify Hashtag/Location/Keyword actors
    │          → lista de usernames
    ▼
[Profile Scrape] → Apify Profile actor (cheap, all usernames)
    │              → Creator dataclasses → DB (upsert)
    ▼
[Initial Filter] → followers range, bio keywords, business, ratio, email, category
    │              → passed / failed → failed marcados "excluded" no DB
    ▼
[Post Scrape] → Apify Posts actor (expensive, only passed[:max_scrape])
    │           → Post dataclasses → DB (upsert)
    ▼
[Analysis] → avg_engagement, posts_last_30_days, posting_frequency, is_active
    │         → keyword irrelevance check → Creator atualizado no DB
    ▼
[Niche Classifier] → GPT fine-tuned → niche label → Creator atualizado no DB
    ▼
[AI Filter] → GPT-4o-mini com critério customizável → ai_filter_pass + reason
    │          → Creator atualizado no DB
    ▼
[Scoring] → EpicTripScore (5 componentes) → Creator + score_history no DB
```

---

## 2. Fluxo Detalhado — Aba Executar

A aba é dividida em **5 passos visuais** que correspondem diretamente a flags do CLI.

### Passo 1 — Seeds
- Lê `search_configs` do DB para a plataforma selecionada
- Modos: todas as ativas / filtrar por tag / seleção manual
- Gera `--seed-ids` como argumento para o CLI

### Passo 2 — Coletar Creators
- Slider: quantidade de profiles (10–200)
- Executa: `pipeline.runner --profiles-only --limit N [--seed-ids ...]`
- Roda `discover()` → Apify → upsert no DB
- Para antes do filtro inicial (nenhum custo de posts)

### Passo 3 — Filtro Inicial (preview ao vivo, sem custo)
- Campos editáveis: followers min/max, posts totais, ratio, business, email, categorias excluídas
- **Preview em tempo real**: conta quantos creators do DB passariam com os filtros atuais
- Os valores são passados como args CLI no Passo 4

### Passo 4 — Scrapar Posts (display only, sem botão próprio)
- Sliders: `max_scrape` (cap de creators) e `max_posts` (posts por creator)
- Estimativa de custo baseada no preview do Passo 3
- **Sem botão separado**: este passo é executado junto com o Passo 5

### Passo 5 — AI Filter & Score
- `text_area` com critério customizável (usa `_DEFAULT_CRITERIA` como base)
- Slider: `max_ai_filter`
- Botão: "🤖 Executar AI Filter" → `pipeline.runner --skip-scrape --max-ai-filter N`
- **ATENÇÃO**: este botão executa apenas análise + AI filter + scoring (sem scraping)

### Resultados (abaixo do Passo 5)
- Tabela dos creators com `ai_filter_pass IS NOT NULL`
- Coluna "Marcar" → insere em `outreach` com status `contacted`
- Download CSV

---

## 3. Mapeamento CLI ↔ Dashboard

| Botão no Dashboard | Comando gerado |
|---|---|
| ⬇️ Executar Coleta | `pipeline.runner --profiles-only --limit N [--seed-ids ...]` |
| 🤖 Executar AI Filter | `pipeline.runner --skip-scrape --max-ai-filter N [--ai-criteria ...]` |

---

## 4. Gaps e Pontos Desconectados

### GAP 1 — Passo 4 não tem botão próprio (scraping de posts nunca roda isolado)
**Problema**: O scraping de posts (`--scrape-only`) não tem botão na aba Executar.  
O botão "Executar Coleta" usa `--profiles-only` (só perfis, sem posts).  
O botão "AI Filter" usa `--skip-scrape` (pula Apify).  
**Resultado**: posts nunca são scrapados via dashboard. O pipeline completo (profiles → filter → posts → analysis → AI → score) só funciona via CLI.

**Conexão faltando**: precisa de um botão "Scrapar Posts" que passe os filtros do Passo 3 e execute:
```
pipeline.runner --scrape-only --max-scrape N --max-posts N 
  --min-followers X --max-followers Y --excluded-keywords "..." etc.
```

### GAP 2 — Filtros do Passo 3 não são passados ao CLI
**Problema**: O Passo 3 mostra um preview ao vivo dos filtros, mas os valores editados (`filt_min_f`, `filt_max_f`, `filt_keywords`, etc.) **não são enviados** ao comando CLI do Passo 5.  
O Passo 5 executa `--skip-scrape` que não usa initial_filter — então o estado visual do Passo 3 é apenas decorativo para o fluxo atual.  
**Impacto**: usuário edita filtros no Passo 3, vê o preview, mas o pipeline roda com os defaults do `config/filters.py`.

### GAP 3 — `search.py` vs `seeds.py` são páginas duplicadas
**Problema**: existem dois arquivos com funcionalidade idêntica:
- `dashboard/pages/seeds.py` → rota `seeds` no `app.py` (nav: "🔍 Busca")
- `dashboard/pages/search.py` → arquivo existente mas **não está no `_NAV` do `app.py`**, portanto inacessível

`search.py` é uma versão mais simples (sem tags, sem inline editor). É código morto.

### GAP 4 — `calibration.py` está inacessível
**Problema**: `dashboard/pages/calibration.py` existe com lógica completa de filtros e re-avaliação, mas **não está mapeada no `_NAV`** de `app.py`.  
Ela não é renderizável via dashboard. É código morto.  
O botão "Run AI Re-evaluation" dentro dela tem o warning: `"Connect to pipeline.ai_filter to implement."` — ou seja, a funcionalidade nunca foi conectada.

### GAP 5 — AI Filter não carrega captions e hashtags no runner
**Problema**: Em `pipeline/runner.py` (Step 4 — AI Filter), o payload enviado ao `evaluate_batch()` tem `captions=[]` e `hashtags=[]` hardcoded:

```python
# runner.py linha ~405
to_filter = [
    {
        "id": c.id,
        "bio": c.bio or "",
        "niche": c.niche or "",
        "captions": [],   # ← SEMPRE VAZIO
        "hashtags": [],   # ← SEMPRE VAZIO
    }
    ...
]
```

O GPT recebe apenas bio + nicho. Captions e hashtags (que estão no DB) nunca são enviados, mesmo que o prompt mencione "Recent captions" e "Hashtags" no `user_message` de `ai_filter.py`.

### GAP 6 — Passo 3 preview ignora creators já "excluded"
**Problema**: O preview do Passo 3 em `run.py` faz SELECT em todos os creators da plataforma sem filtrar `status != 'excluded'`. Creators já excluídos em runs anteriores são contados no total e no preview, inflando o número "passariam".

```python
# run.py linha ~253
all_profiles = conn.execute(
    "SELECT followers, following, is_private, bio, business_account, "
    "total_posts, email, category FROM creators WHERE platform=?",
    (platform,),
).fetchall()
```

### GAP 7 — OpenAI cost tracking subestimado
**Problema**: O custo OpenAI em `runner.py` é calculado como `len(evaluated) * 0.0001` (custo fixo por chamada). O custo real do niche classifier (GPT fine-tuned) **nunca é contabilizado** — só o AI filter.  
`pipeline_runs.openai_cost_usd` reflete apenas ~metade do custo real.

### GAP 8 — `niche_classifier.py` roda em todo `--skip-scrape`
**Problema**: No fluxo `--skip-scrape`, o runner busca todos os creators do banco (incluindo os já com niche), mas a condição `if creator.niche: continue` só pula re-classificação se já foi feita. Porém todos os creators `status = 'excluded'` **também passam pelo loop de niche classification** antes do check de status:

```python
# runner.py linha ~360
db_creators = get_all_creators(conn, platform=platform)
for creator in db_creators:
    if creator.status == "excluded" or creator.id is None:
        continue
    if creator.niche:
        continue  # já classificado
```

O check de `status == "excluded"` está na linha correta, mas creators que **acabaram de ser excluídos pelo keyword check** no loop anterior (Step 2 de análise) ainda aparecem na nova chamada de `get_all_creators` do Step 3 porque essa query não filtra por `status`.  
Porém `get_all_creators` carrega TUDO do banco sem filtro de status — creators excluídos de runs anteriores são re-processados até a linha do `if creator.status == "excluded"`. Performance desnecessária com banco grande.

### GAP 9 — `RUN_PASSWORD` default inseguro
**Problema**: `config/settings.py`:
```python
RUN_PASSWORD: str = os.getenv("RUN_PASSWORD", "123123")
```
Se `.env` não definir `RUN_PASSWORD`, a senha padrão é `123123`. Não há alerta no dashboard se a senha default estiver em uso.

### GAP 10 — `get_connection()` usa `check_same_thread=False` sem pool
**Problema**: `db/connection.py` abre a conexão com `check_same_thread=False`. O dashboard usa `@st.cache_resource` para reutilizar a mesma conexão em todas as abas/reruns. Streamlit pode rodar callbacks em threads diferentes, especialmente com `st.data_editor` e botões. SQLite em modo WAL seria mais seguro.

---

## 5. Bugs

### BUG 1 — `upsert_creator` perde status em re-runs (CRÍTICO)
**Arquivo**: `db/repository.py` linha ~71  
**Problema**: O `ON CONFLICT ... DO UPDATE` usa:
```sql
status = COALESCE(excluded.status, creators.status)
```
Quando `upsert_creator` é chamado com um Creator recém-criado (status padrão = `'discovered'`), ele **sobrescreve** um creator que tinha `status = 'excluded'`. O COALESCE protege apenas contra NULL, não contra o valor `'discovered'`.

**Cenário**: creator foi excluído em run anterior → nova run faz profile scrape → `normalize_profile` retorna Creator com `status='discovered'` → upsert sobrescreve `'excluded'` para `'discovered'`.

**Correção**:
```sql
status = CASE 
    WHEN creators.status = 'excluded' THEN creators.status 
    ELSE COALESCE(excluded.status, creators.status) 
END
```

### BUG 2 — `_posts_instagram` usa `creator_id=0` para todos os posts
**Arquivo**: `pipeline/scraping.py` linha ~83  
**Problema**:
```python
post = normalize_post(raw, creator_id=0)
post._owner_username = (raw.get("ownerUsername") or "").lower()
```
O `creator_id=0` é um placeholder inválido. Em seguida, o runner faz lookup via `_owner_username` para obter o `creator_id` real. Se o username não estiver no `username_to_id` (ex: scrape retornou username com case diferente), `cid = None` e o post é **silenciosamente descartado** sem log.

```python
# runner.py linha ~289
cid = username_to_id.get(owner.lower())
if cid:
    post.creator_id = cid
    upsert_post(conn, post)
# senão: post perdido sem aviso
```

**Correção**: adicionar `logger.warning("Post descartado: username '%s' não encontrado", owner)` quando `cid is None`.

### BUG 3 — `is_niche_irrelevant` usa substring match, não word boundary
**Arquivo**: `pipeline/niche_classifier.py` linha ~50  
**Problema**:
```python
if kw.lower() in niche_lower:
    return True
```
Keywords como `"food"` na lista de `EXCLUDED_KEYWORDS` vão marcar como irrelevante qualquer nicho que contenha `"food"` como substring (ex: `"seafood travel"`, `"outdoor food photography"`).  
O `is_irrelevant_by_keywords` em `analysis.py` usa corretamente `\b` word boundaries, mas `is_niche_irrelevant` não.

### BUG 4 — `score_followers` hardcoda `min_f=800` ignorando config
**Arquivo**: `pipeline/scoring.py` linha ~24  
**Problema**: `score_followers(count, min_f=800, max_f=50000)` tem valores hardcoded. O Instagram config em `config/filters.py` tem `min_followers: 800` e `max_followers: 7000`, mas o scoring usa `max_f=50000` que é o valor do TikTok. Creators Instagram com 10k–50k recebem score não-zero, mesmo que o initial filter os tivesse excluído.

### BUG 5 — `overview.py` conta `ai_filter_pass` incorretamente
**Arquivo**: `dashboard/pages/overview.py` linha ~22  
**Problema**:
```python
qualified = int(df["ai_filter_pass"].sum())
```
SQLite armazena booleanos como `0/1`. Com pandas, `sum()` vai somar os valores numéricos corretamente, mas se `ai_filter_pass` for `None` (NULL), pandas retorna `NaN` na soma e converte para `int` pode ser incorreto dependendo da versão.  
**Forma segura**:
```python
qualified = int((df["ai_filter_pass"] == 1).sum())
```

### BUG 6 — `_apify_usage()` usa `requests` não declarado em `requirements.txt`
**Arquivo**: `platforms/apify_client.py` linha ~73  
**Problema**:
```python
import requests as _requests
```
O `requests` não está em `requirements.txt`. Funciona apenas se instalado indiretamente por outro pacote (ex: `apify-client` depende dele). Se a dependência transitiva for removida, o sidebar quebra silenciosamente (capturado pelo `except Exception` em `app.py`).

---

## 6. Fluxo Completo Esperado vs. Atual

| Etapa | Esperado | Atual | Status |
|---|---|---|---|
| 1. Seeds | Configurar hashtags/keywords | ✅ Funciona (seeds.py) | OK |
| 2. Profile Scrape | Botão "Coletar" → só perfis | ✅ Funciona | OK |
| 3. Initial Filter | Preview ao vivo + passar filtros ao CLI | ⚠️ Preview OK, filtros não passados ao CLI | GAP 2 |
| 4. Post Scrape | Botão próprio com filtros aplicados | ❌ Sem botão — nunca roda via dashboard | GAP 1 |
| 5. Analysis | Auto após post scrape | ✅ Roda no `--skip-scrape` | OK |
| 6. Niche Classification | GPT fine-tuned | ✅ Funciona | OK (GAP 5) |
| 7. AI Filter | GPT-4o-mini com bio+captions+hashtags | ⚠️ Roda sem captions/hashtags | GAP 5 |
| 8. Scoring | EpicTripScore gravado no DB | ✅ Funciona | OK |
| 9. Resultados | Tabela com leads + marcar contatado | ✅ Funciona | OK |
| 10. Leads | Gestão de status por creator | ✅ Funciona (leads.py) | OK |

---

## 7. Prioridade de Correções

### Crítico
1. **BUG 1** — `upsert_creator` sobrescreve `status=excluded` com `status=discovered`
2. **GAP 1** — Post scraping nunca roda via dashboard (fluxo principal quebrado)

### Alto
3. **GAP 2** — Filtros do Passo 3 não são passados ao CLI
4. **GAP 5** — AI Filter roda sem captions e hashtags
5. **BUG 3** — `is_niche_irrelevant` sem word boundary

### Médio
6. **GAP 3** — `search.py` é código morto (duplicata inacessível)
7. **GAP 4** — `calibration.py` é código morto e AI Re-evaluation não implementada
8. **BUG 2** — Posts descartados silenciosamente quando username não encontrado
9. **BUG 4** — `score_followers` usa `max_f` errado para Instagram

### Baixo
10. **GAP 6** — Preview do Passo 3 inclui creators já excluídos
11. **GAP 7** — OpenAI cost tracking incompleto (niche classifier não contabilizado)
12. **GAP 8** — Performance: creators excluídos re-processados desnecessariamente
13. **GAP 9** — Senha default insegura `123123`
14. **BUG 5** — `ai_filter_pass.sum()` frágil com nulls
15. **BUG 6** — `requests` não em `requirements.txt`

---

## 8. Referência Rápida de Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `dashboard/app.py` | Entry point Streamlit, roteamento de páginas |
| `dashboard/pages/run.py` | **Coração do dashboard** — 5 passos do pipeline |
| `dashboard/pages/seeds.py` | Gestão de search seeds com tags |
| `dashboard/pages/leads.py` | Gestão de leads com status workflow |
| `dashboard/pages/overview.py` | KPIs e gráficos gerais |
| `dashboard/pages/profiles.py` | Tabela completa com score breakdown |
| `dashboard/pages/search.py` | ⚠️ CÓDIGO MORTO — inacessível no nav |
| `dashboard/pages/calibration.py` | ⚠️ CÓDIGO MORTO — inacessível no nav |
| `pipeline/runner.py` | Orquestrador CLI — entry point do pipeline |
| `pipeline/discovery.py` | Lê seeds do DB → chama Apify |
| `pipeline/scraping.py` | Normaliza dados Apify → Creator/Post |
| `pipeline/initial_filter.py` | Filtro rápido por profile (sem posts) |
| `pipeline/analysis.py` | Métricas de engajamento e atividade |
| `pipeline/niche_classifier.py` | GPT fine-tuned → label de nicho |
| `pipeline/ai_filter.py` | GPT-4o-mini → PASSA/NÃO PASSA |
| `pipeline/scoring.py` | EpicTripScore (5 componentes) |
| `platforms/apify_client.py` | Wrapper genérico Apify (blocking .call()) |
| `platforms/instagram.py` | Discovery + scraping Instagram |
| `platforms/tiktok.py` | Discovery + scraping TikTok |
| `db/connection.py` | get_connection() + auto-migrations |
| `db/repository.py` | CRUD completo |
| `db/schema.sql` | 6 tabelas: creators, posts, pipeline_runs, score_history, outreach, search_configs |
| `config/settings.py` | Variáveis de ambiente |
| `config/filters.py` | Thresholds por plataforma + keyword lists |
| `config/seeds.py` | Seeds padrão (carregados uma vez no DB vazio) |
