# Melhorias: Campo "Pass" na UI + Export CSV completo

## Problema 1 — Campo "Pass/Fail" não aparece na tabela de Leads

### Sintoma
A coluna `AI ✓` exibe `False` como string sem distinção visual de `None` (não avaliado). Não há ícone nem cor.

### Causa (arquivo exato)
**`dashboard/pages/leads.py`, linhas 99–119.**

A coluna `ai_filter_pass` é passada crua para `st.dataframe()`. O Streamlit renderiza:
- `True` → string `"True"`
- `False` → string `"False"` (sem destaque visual)
- `None` → célula vazia

Não há mapeamento antes de montar `display_df`.

### Solução
Mapear a coluna **antes** de passar ao dataframe, em `leads.py` logo antes da linha 119:

```python
# Mapear ai_filter_pass para exibição visual — ANTES do rename
if "ai_filter_pass" in df.columns:
    df["ai_filter_pass"] = df["ai_filter_pass"].map(
        {True: "✅ Pass", False: "❌ Fail"}
    ).fillna("—")
```

Os três estados ficam:

| Valor no DB | Exibição |
|-------------|----------|
| `True`      | ✅ Pass  |
| `False`     | ❌ Fail  |
| `NULL`      | —        |

---

## Problema 2 — Export CSV incompleto (falta dados de posts e perfil completo)

### Sintoma
O CSV exportado (`creators_instagram.csv`) contém apenas:
```
pass, username, display_name, followers, niche, email, link_in_bio, score, avg_engagement, posts_last_30d, ai_reason, contacted_at
```

Faltam dados importantes de perfil e de posts.

### Dados faltantes identificados

**Do perfil (tabela `creators`):**
- `bio` — biografia completa
- `category` — categoria do Instagram
- `profile_url` / `link_in_bio` (já existe, mas verificar se está sendo exportado corretamente)
- `posting_frequency`
- `is_active`
- `posts_scraped_count` (total de posts no banco)

**De posts (tabela `posts` — todos scraped e salvos no banco):**

O modelo `Post` já coleta e armazena os seguintes campos — todos disponíveis via JOIN:

| Campo DB | Descrição | Disponível? |
|----------|-----------|-------------|
| `caption` | Texto completo do post | ✅ sim |
| `hashtags` | JSON array de hashtags | ✅ sim |
| `post_url` | URL direta do post (`/p/<shortcode>/`) | ✅ sim |
| `post_type` | `image`, `video`, `sidecar` | ✅ sim |
| `likes` | Total de likes | ✅ sim |
| `comments` | Total de comentários | ✅ sim |
| `views` | Views (reels/vídeos) | ✅ sim |
| `engagement_rate` | Engajamento por post | ✅ sim |
| `published_at` | Data de publicação | ✅ sim |

**Agregados calculáveis por creator:**
- `posts_scraped_total` — COUNT de posts no banco
- `avg_likes` — AVG(likes)
- `avg_comments` — AVG(comments)
- `last_post_date` — MAX(published_at)
- `top_hashtags` — flatten + frequência dos JSON arrays
- `sample_captions` — 2-3 captions mais recentes (concat com " | ")

### Solução — Query agregada para o export

Uma única query com `LEFT JOIN` e `string_agg` — evita N+1 queries:

```sql
SELECT
    c.id,
    c.username,
    c.display_name,
    c.followers,
    c.bio,
    c.category,
    c.location,
    c.niche,
    c.email,
    c.link_in_bio,
    c.avg_engagement,
    c.posting_frequency,
    c.posts_last_30_days,
    c.is_active,
    c.ai_filter_pass,
    c.ai_filter_reason,
    c.epic_trip_score        AS score,
    o.last_contacted_at,
    COUNT(p.id)              AS posts_scraped_total,
    MAX(p.published_at)      AS last_post_date,
    AVG(p.likes)             AS avg_likes,
    AVG(p.comments)          AS avg_comments,
    string_agg(
        CASE WHEN p.caption IS NOT NULL
             THEN left(p.caption, 100) END,
        ' | '
        ORDER BY p.published_at DESC
    ) FILTER (WHERE p.caption IS NOT NULL) AS sample_captions
FROM creators c
LEFT JOIN posts p ON p.creator_id = c.id
LEFT JOIN (
    SELECT creator_id, MAX(contacted_at) AS last_contacted_at
    FROM outreach GROUP BY creator_id
) o ON o.creator_id = c.id
WHERE c.platform = %(platform)s
GROUP BY c.id, o.last_contacted_at
ORDER BY c.epic_trip_score DESC NULLS LAST;
```

**Notas sobre o schema real (`db/schema.sql`):**
- Coluna de likes: `p.likes` (não `p.likes_count`)
- Coluna de comentários: `p.comments` (não `p.comments_count`)
- `contacted_at` **não existe** em `creators` — fica em `outreach.contacted_at`, daí o LEFT JOIN acima

### Colunas finais sugeridas para o CSV

```
id, ai_filter_pass, username, display_name, followers, bio, category, location, niche,
email, link_in_bio, score, avg_engagement, avg_likes, avg_comments,
posts_last_30_days, posts_scraped_total, posting_frequency, last_post_date,
sample_captions, ai_filter_reason, is_active, last_contacted_at
```

---

## Problema 3 — Contexto insuficiente enviado para a IA

### O que a IA recebe hoje

Em `runner.py` (linhas 501–524), o dict montado para cada creator é:

```python
{
    "id": c.id,
    "bio": c.bio or "",
    "niche": c.niche or "",
    "captions": captions_ai,    # SELECT caption LIMIT 10
    "hashtags": hashtags_ai,    # SELECT hashtags LIMIT 10
    # FALTAM: display_name, followers, category, location,
    #         link_in_bio, business_account, avg_engagement,
    #         posts_last_30_days, posts com métricas por post
}
```

> **Nota:** `display_name` já existe em `c` no momento da montagem (`runner.py:516`) mas não é incluído no dict — é a mudança de **menor custo com maior ganho de contexto**.

Em `ai_filter.py` (linhas 53–61), o `user_message` final enviado ao modelo é:

```
Bio: <bio>
Niche: <niche>
Recent captions: <captions[:5] truncados em 600 chars>
Hashtags: <hashtags[:30] truncados em 300 chars>
```

Além disso, o system prompt e user message são **concatenados numa única mensagem `role: user`** (linha 64), o que reduz a aderência do modelo às instruções de formato JSON. Deve ser separado em `role: system` + `role: user`.

### O que está disponível no banco mas NÃO é enviado

**Do perfil (`creators`):**

| Campo | Por que ajuda a IA |
|-------|--------------------|
| `display_name` | Nome real — contexto cultural/geográfico |
| `followers` | Volume de audiência — relevante para qualificação |
| `category` | Categoria do Instagram (ex: "Personal Blog", "Artist") |
| `location` | Localização geográfica declarada |
| `link_in_bio` | URL externa — indica tipo de conta (loja, agência, blog) |
| `verified` | Conta verificada — muda o critério |
| `business_account` | Conta comercial — pode ser fator de exclusão |
| `avg_engagement` | Engajamento médio calculado |
| `posts_last_30_days` | Atividade recente |
| `posting_frequency` | Frequência de postagem |

**Dos posts (`posts`) — além de caption e hashtags:**

| Campo | Por que ajuda a IA |
|-------|--------------------|
| `post_url` | Link direto — verificabilidade |
| `post_type` | image/video/sidecar — padrão de conteúdo |
| `likes` | Volume de engajamento por post |
| `comments` | Comentários — indicador de comunidade |
| `views` | Alcance em reels/vídeos |
| `published_at` | Data — verificar consistência e recência |

### Solução — `user_message` completo

O `evaluate_creator()` em `ai_filter.py` deve receber e usar todos os campos disponíveis:

```python
def evaluate_creator(
    bio: str,
    niche: str,
    captions: list[str],
    hashtags: list[str],
    *,
    # novos campos de perfil
    display_name: str = "",
    followers: int = 0,
    category: str = "",
    location: str = "",
    link_in_bio: str = "",
    business_account: bool = False,
    avg_engagement: float = 0.0,
    posts_last_30_days: int = 0,
    # novos campos de posts
    posts_detail: list[dict] | None = None,  # lista de {url, type, likes, comments, views, date}
    criteria: str | None = None,
) -> tuple[bool | None, str]:
```

E o `user_message` ficaria:

```
Creator: <display_name> (@<username>)
Followers: <followers>
Category: <category>
Location: <location>
Business account: <yes/no>
Link in bio: <link_in_bio>
Bio: <bio>
Niche: <niche>
Avg engagement: <avg_engagement>
Posts last 30 days: <posts_last_30_days>

Recent posts (up to 10):
1. [<date>] <post_type> | ❤️ <likes> 💬 <comments> 👁 <views> | <post_url>
   Caption: <caption[:200]>
   Hashtags: <hashtags>
2. ...

Top hashtags overall: <top hashtags agregados>
```

### Estimativa de custo de tokens

| Cenário | Tokens/creator | Total (30 creators) | Custo aprox. (gpt-4o-mini) |
|---------|---------------|---------------------|----------------------------|
| Atual (4 campos) | ~200–400 | ~12K | ~$0.002 |
| Com perfil completo + métricas por post (sem URL, caption 100 chars) | ~500–700 | ~21K | ~$0.003 |
| Com 10 posts completos (caption longa + URL + hashtags) | ~800–1.200 | ~36K | ~$0.005 |

**Recomendação:** usar o cenário intermediário — perfil completo + métricas numéricas por post + captions curtas (100 chars). Omitir URLs e hashtags repetidas por post (já agregadas no topo). Custo aumenta ~1.5×, qualidade melhora significativamente.

### Por que isso melhora a qualidade do filtro

- A IA hoje toma decisão baseada em ~4 campos. Com o contexto completo, ela avalia:
  - Se é conta pessoal ou comercial (`business_account`, `category`, `link_in_bio`)
  - Se o conteúdo é autêntico (captions + métricas reais por post)
  - Se a audiência é real (relação seguidores/engajamento)
  - Se é ativo e consistente (`posts_last_30_days`, datas dos posts)

---

## Arquivos a modificar

| Arquivo | O que mudar |
|---------|------------|
| `dashboard/pages/leads.py:99–119` | Mapear `ai_filter_pass` com `.map()` antes de `display_df` |
| `dashboard/pages/leads.py:192` | Substituir `df[display_cols]` por query com JOIN + string_agg |
| `pipeline/ai_filter.py:36–72` | Separar `role:system`/`role:user`; enriquecer assinatura com campos de perfil e posts |
| `pipeline/runner.py:516–524` | Incluir `display_name`, `followers`, `category`, `location`, `business_account`, `avg_engagement`, `posts_last_30_days` e lista de posts com métricas no dict para `evaluate_batch` |
