# Como a Resposta da IA vira Lista Excel

> Rastreamento completo: resposta GPT → DB → Dashboard → CSV exportável

---

## Fluxo Visual

```
┌─────────────────────────────────────────────────────────────┐
│ PASSO 5: Usuário clica "🤖 Executar AI Filter"              │
│ Input: Critério de avaliação (text area)                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ AI Filter (pipeline/ai_filter.py → evaluate_batch)          │
│                                                              │
│ Para cada creator:                                           │
│   Input: { bio, niche, captions[:5], hashtags[:30] }       │
│   ↓                                                          │
│   GPT-4o-mini responde:                                      │
│   {                                                          │
│     "pass": true ou false,                                   │
│     "reason": "Authentic mochilero sharing budget tips..."   │
│   }                                                          │
│   ↓                                                          │
│   Output: { id, ai_filter_pass, ai_filter_reason }         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Persistência no DB (db/repository.py)                       │
│                                                              │
│ UPDATE creators SET                                          │
│   ai_filter_pass = 1 (ou 0),                                │
│   ai_filter_reason = "Authentic mochilero..."               │
│ WHERE id = <creator_id>                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Dashboard Query (dashboard/pages/run.py, linha 575)          │
│                                                              │
│ SELECT c.id, c.username, c.display_name, c.followers,      │
│        c.niche, c.email, c.link_in_bio,                    │
│        c.ai_filter_pass, c.ai_filter_reason,               │
│        c.epic_trip_score, c.avg_engagement,                │
│        c.posts_last_30_days, MAX(o.contacted_at)           │
│ FROM creators c                                             │
│ LEFT JOIN outreach o ON o.creator_id = c.id                │
│ WHERE c.platform = ? AND c.ai_filter_pass IS NOT NULL      │
│ ORDER BY c.epic_trip_score DESC                            │
│                                                              │
│ ✅ Filtra APENAS creators com ai_filter_pass definido       │
│ ✅ Ordena por score (melhor primeiro)                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Conversão para DataFrame (pandas)                           │
│                                                              │
│ df = pd.DataFrame([dict(r) for r in result_rows])          │
│                                                              │
│ Colunas no DataFrame:                                        │
│   id, username, display_name, followers, niche,            │
│   email, link_in_bio, ai_filter_pass, ai_filter_reason,    │
│   epic_trip_score, avg_engagement, posts_last_30_days,     │
│   contacted_at                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Formatação para Display no Dashboard (linhas 595–601)       │
│                                                              │
│ df["Pass"] = df["ai_filter_pass"].map({1: "✅", 0: "❌"})  │
│ df["Score"] = f"{epic_trip_score:.2f}"                      │
│ df["Eng."] = f"{avg_engagement*100:.1f}%"                   │
│ df["Posts/30d"] = posts_last_30_days                        │
│ df["Followers"] = f"{followers:,}"                          │
│                                                              │
│ Resultado: tabela visual bonita no dashboard                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Exportação para CSV (linhas 611–623)                        │
│                                                              │
│ csv_df = df[["ai_filter_pass", "username",                 │
│              "display_name", "followers", "niche",          │
│              "email", "link_in_bio", "epic_trip_score",     │
│              "avg_engagement", "posts_last_30_days",        │
│              "ai_filter_reason", "contacted_at"]]           │
│                                                              │
│ csv_df.columns = ["pass", "username", "display_name",      │
│                   "followers", "niche", "email",            │
│                   "link_in_bio", "score",                   │
│                   "avg_engagement", "posts_last_30d",       │
│                   "ai_reason", "contacted_at"]              │
│                                                              │
│ st.download_button("⬇️ Exportar CSV")                       │
│   → creators_instagram.csv ou creators_tiktok.csv           │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    📊 EXCEL LIMPO
```

---

## Exemplo Real: Do GPT ao CSV

### 1️⃣ Resposta da GPT (JSON)

```json
{
  "pass": true,
  "reason": "Authentic mochilero sharing budget tips across Latin America with consistent engagement."
}
```

### 2️⃣ Salvo no DB

```sql
UPDATE creators SET
  ai_filter_pass = 1,
  ai_filter_reason = 'Authentic mochilero sharing budget tips across Latin America with consistent engagement.'
WHERE id = 42;
```

### 3️⃣ Lido do DB (Query SQL)

```
id: 42
username: juan_travels
display_name: Juan García
followers: 3500
niche: mochilero travel
email: juan@email.com
link_in_bio: https://linktr.ee/juan
ai_filter_pass: 1
ai_filter_reason: Authentic mochilero sharing budget tips...
epic_trip_score: 0.78
avg_engagement: 0.087
posts_last_30_days: 8
contacted_at: NULL
```

### 4️⃣ Formatado no Dashboard (HTML table)

| Pass | Username | Followers | Nicho | Score | Eng. | Posts/30d | Motivo IA |
|---|---|---|---|---|---|---|---|
| ✅ | juan_travels | 3,500 | mochilero travel | 0.78 | 8.7% | 8 | Authentic mochilero sharing budget tips... |

### 5️⃣ Exportado para CSV (Excel)

```csv
pass,username,display_name,followers,niche,email,link_in_bio,score,avg_engagement,posts_last_30d,ai_reason,contacted_at
1,juan_travels,Juan García,3500,mochilero travel,juan@email.com,https://linktr.ee/juan,0.78,0.087,8,Authentic mochilero sharing budget tips...,
```

---

## Filtros Aplicados no Caminho

### ✅ Quem entra na lista Excel?

1. **`ai_filter_pass IS NOT NULL`** — Só creators que foram avaliados pela IA
2. **Ordenado por `epic_trip_score DESC`** — Melhores leads primeiro
3. **Coluna `pass` = 1 ou 0** — Visível no CSV (1 = aprovado, 0 = rejeitado)

### ❌ Quem NÃO entra?

- Creators com `ai_filter_pass = NULL` (não foram avaliados ainda)
- Creators com status `"excluded"` (foram filtrados antes)
- Creators sem posts (não têm dados para análise)

---

## Estrutura do CSV Final

| Coluna | Origem | Tipo | Exemplo |
|---|---|---|---|
| `pass` | `ai_filter_pass` (1/0) | Integer | 1 |
| `username` | `creators.username` | String | juan_travels |
| `display_name` | `creators.display_name` | String | Juan García |
| `followers` | `creators.followers` | Integer | 3500 |
| `niche` | `creators.niche` (GPT) | String | mochilero travel |
| `email` | `creators.email` | String | juan@email.com |
| `link_in_bio` | `creators.link_in_bio` | String | https://linktr.ee/juan |
| `score` | `epic_trip_score` | Float (2 decimais) | 0.78 |
| `avg_engagement` | `creators.avg_engagement` | Float | 0.087 |
| `posts_last_30d` | `creators.posts_last_30_days` | Integer | 8 |
| `ai_reason` | `ai_filter_reason` (GPT) | String | Authentic mochilero sharing... |
| `contacted_at` | `outreach.contacted_at` | ISO datetime | 2026-03-15T10:30:00 |

---

## Lógica de Conversão: `pass` (1/0) → Excel

```python
# No DB: ai_filter_pass é INTEGER (1 ou 0)
ai_filter_pass = 1  # True
ai_filter_pass = 0  # False

# No CSV: mantém como 1 ou 0
csv_df["pass"] = df["ai_filter_pass"]
# Resultado: coluna "pass" com valores 1 ou 0

# No Dashboard: converte para emoji para visualização
df["Pass"] = df["ai_filter_pass"].map({1: "✅", 0: "❌"})
# Resultado: coluna "Pass" com ✅ ou ❌
```

---

## Fluxo Completo em Código

### 1. AI Filter retorna resposta JSON

```python
# pipeline/ai_filter.py
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "system", "content": criteria}, ...],
    response_format={"type": "json_object"},
)
data = json.loads(response.choices[0].message.content)
# data = {"pass": true, "reason": "..."}
```

### 2. Salva no DB

```python
# pipeline/runner.py
update_creator_ai_filter(
    conn,
    creator_id=42,
    ai_filter_pass=data["pass"],        # True → 1
    ai_filter_reason=data["reason"],
)
```

### 3. Query SQL filtra

```python
# dashboard/pages/run.py, linha 575
result_rows = conn.execute(
    """
    SELECT ... c.ai_filter_pass, c.ai_filter_reason ...
    FROM creators c
    WHERE c.ai_filter_pass IS NOT NULL
    ORDER BY c.epic_trip_score DESC
    """
).fetchall()
```

### 4. Converte para DataFrame

```python
df = pd.DataFrame([dict(r) for r in result_rows])
# df["ai_filter_pass"] = [1, 0, 1, 1, 0, ...]
# df["ai_filter_reason"] = ["Authentic...", "Not relevant...", ...]
```

### 5. Formata para CSV

```python
csv_df = df[["ai_filter_pass", "username", ..., "ai_filter_reason"]].copy()
csv_df.columns = ["pass", "username", ..., "ai_reason"]
csv_df.to_csv(index=False)
# Resultado: creators_instagram.csv
```

---

## Resumo: Como Funciona o Filtro

| Etapa | Entrada | Processamento | Saída |
|---|---|---|---|
| **GPT** | Bio, captions, hashtags, niche | Avalia contra critério do usuário | `{"pass": true/false, "reason": "..."}` |
| **DB** | JSON da GPT | `UPDATE creators SET ai_filter_pass = 1/0` | Coluna `ai_filter_pass` (1 ou 0) |
| **Query** | Tabela `creators` | `WHERE ai_filter_pass IS NOT NULL` | Apenas creators avaliados |
| **DataFrame** | Rows do DB | `pd.DataFrame()` | Coluna `ai_filter_pass` com valores 1/0 |
| **CSV** | DataFrame | `to_csv()` + renomear coluna | Coluna `pass` com valores 1/0 |
| **Excel** | CSV | Abrir em Excel/Sheets | ✅ Lista limpa e pronta para usar |

---

## Resultado Final no Excel

Você abre o CSV e vê:

```
pass | username      | followers | niche            | score | ai_reason
-----|---------------|-----------|------------------|-------|------------------------------------------
1    | juan_travels  | 3500      | mochilero travel | 0.78  | Authentic mochilero sharing budget tips
1    | maria_viaja   | 2100      | budget backpack  | 0.72  | Consistent low-cost travel content
0    | luxury_life   | 8500      | luxury travel    | 0.45  | Focuses on high-end experiences
1    | alex_nomad    | 1800      | nomad lifestyle  | 0.68  | Independent creator, authentic journey
```

**Pronto para:**
- ✅ Filtrar por `pass = 1` (só aprovados)
- ✅ Ordenar por `score` (melhores leads)
- ✅ Copiar emails para contato
- ✅ Ler `ai_reason` para entender por que passou/falhou
