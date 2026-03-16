# Deploy no Render

Draper roda no Render como um **Web Service** (Streamlit) + **PostgreSQL** gerenciado.

---

## Pré-requisitos

- Conta no [render.com](https://render.com)
- Repositório no GitHub com o código do projeto
- Tokens: `APIFY_API_TOKEN`, `OPENAI_API_KEY`

---

## Passo 1 — Criar o banco PostgreSQL

1. No dashboard do Render, clique em **New → PostgreSQL**
2. Preencha:

| Campo | Valor |
|-------|-------|
| **Name** | `draper-postgres` |
| **Database** | `draper` |
| **User** | `draper` |
| **Region** | mesma região do Web Service (ex: Oregon) |
| **Plan** | Free (90 dias) ou Starter ($7/mês) |

3. Clique em **Create Database**
4. Após criar, copie o valor de **Internal Database URL** — você vai usar no próximo passo.

> Use **Internal URL** (não External) para comunicação entre serviços no mesmo Render region — mais rápido e sem custo de egress.

---

## Passo 2 — Criar o Web Service

1. Clique em **New → Web Service**
2. Conecte o repositório GitHub
3. Preencha:

| Campo | Valor |
|-------|-------|
| **Name** | `draper` |
| **Region** | mesma do banco |
| **Branch** | `main` |
| **Root Directory** | `draper` |
| **Runtime** | Python |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `streamlit run dashboard/app.py --server.port $PORT --server.address 0.0.0.0` |
| **Plan** | Starter ($7/mês) — Free dorme após inatividade |

> **Root Directory** deve ser `draper` se o seu repo tiver a pasta `draper/draper/` aninhada. Ajuste conforme a estrutura real do seu repositório.

---

## Passo 3 — Variáveis de ambiente

No Web Service, vá em **Environment → Add Environment Variable** e adicione:

| Variável | Valor |
|----------|-------|
| `DATABASE_URL` | Internal URL copiada do banco (Passo 1) |
| `APIFY_API_TOKEN` | Seu token Apify |
| `OPENAI_API_KEY` | Sua chave OpenAI |
| `GPT_FILTER_MODEL` | `gpt-4o-mini` |
| `GPT_NICHE_MODEL` | seu modelo fine-tuned (ou `gpt-4o-mini`) |
| `RUN_PASSWORD` | senha para proteção da página Run |
| `LOG_LEVEL` | `INFO` |

> **Não** adicione `PORT` — o Render injeta automaticamente.

---

## Passo 4 — Deploy

1. Clique em **Save Changes** → o Render inicia o primeiro deploy automaticamente
2. Acompanhe os logs em **Logs** — você deve ver:

```
INFO [db.repository] Seeded default search configs from config/seeds.py
```

Isso confirma que a conexão com o banco funcionou e o schema foi aplicado.

3. Acesse a URL pública gerada (ex: `https://draper.onrender.com`)

---

## Rodando o Pipeline no Render

O pipeline (`pipeline/runner.py`) é executado **pelo próprio dashboard** na página **Run**, via subprocess. Ele roda no mesmo container do Streamlit — não é necessário um worker separado.

Para rodar manualmente via Render Shell:

```bash
python -m pipeline.runner --platform instagram --max-scrape 20 --scrape-only
```

---

## Re-deploy após mudanças

Push para o branch `main` dispara deploy automático se o repositório estiver conectado ao Render via GitHub.

Deploy manual:
```bash
git push origin main
```

Ou pelo dashboard: **Manual Deploy → Deploy latest commit**.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'psycopg2'`
Confirme que o **Root Directory** está correto e que o `requirements.txt` está no diretório raiz do serviço.

### `connection refused` ao conectar no banco
- Verifique se usou a **Internal URL** (não External)
- Confirme que banco e web service estão na **mesma região**

### Dashboard abre mas está vazio
Normal no primeiro deploy — o banco está vazio. Rode o pipeline pela página **Run** ou via Render Shell.

### Render dorme o serviço (plano Free)
O plano Free hiberna após 15 min de inatividade. Use o plano **Starter ($7/mês)** para manter sempre ativo.

---

## Arquitetura no Render

```
[GitHub main] ──push──▶ [Render Build]
                              │
                    pip install -r requirements.txt
                              │
                    streamlit run dashboard/app.py
                              │
                     [Web Service :$PORT]
                              │
                    DATABASE_URL (Internal)
                              │
                    [PostgreSQL Managed]
```

O schema e as seeds são aplicados automaticamente na primeira conexão — nenhum passo de migração manual é necessário.
