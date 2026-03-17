# Bug: AI Filter retorna resposta vazia (`{}`) — todos os creators marcados como `invalid_response`

## Sintoma observado

Nos logs do pipeline, o modelo `gpt-5-nano` responde com HTTP 200, mas o conteúdo retornado é literalmente `'{}'`:

```
AI filter raw response [model=gpt-5-nano]: '{}'
WARNING: AI filter response missing 'pass' key. parsed={} raw='{}'
```

Resultado: todos os creators avaliados ficam com `ai_filter_pass = False` e `ai_filter_reason = "invalid_response"`, e nenhum passa pelo filtro (`qualified=0`).

---

## Causa raiz

### 1. Modelo inexistente: `gpt-5-nano`

O modelo configurado via `GPT_FILTER_MODEL` é `gpt-5-nano`, que **não existe na OpenAI**.

A API retorna HTTP 200 com conteúdo `'{}'` (objeto vazio) ao invés de retornar um erro explícito — comportamento silencioso que passa pelo `json.loads` mas não contém a chave `pass`.

**Modelos válidos disponíveis:**
- `gpt-4o-mini` ← recomendado (barato e confiável)
- `gpt-4o`
- `gpt-3.5-turbo`

### 2. A mensagem é enviada inteiramente como `role: user` (sem `role: system`)

Em `ai_filter.py`, linha 64–70, o system prompt e o user message são concatenados e enviados como **uma única mensagem `user`**:

```python
full_message = f"{_build_system_prompt(criteria)}\n\n---\n\n{user_message}"
response = client.chat.completions.create(
    model=GPT_FILTER_MODEL,
    messages=[
        {"role": "user", "content": full_message},  # ← tudo em "user"
    ],
    ...
)
```

Modelos mais fracos/baratos tendem a ignorar instruções de formato JSON quando não vêm num `system` message dedicado. O correto seria:

```python
messages=[
    {"role": "system", "content": _build_system_prompt(criteria)},
    {"role": "user", "content": user_message},
]
```

---

## Evidências nas imagens

| Evidência | Detalhe |
|-----------|---------|
| Log: `AI filter raw response [model=gpt-5-nano]: '{}'` | Modelo retorna objeto vazio |
| Log: `WARNING: AI filter response missing 'pass' key` | JSON parseado como `{}`, sem chave `pass` |
| DB debug: todos com `ai_filter_reason = invalid_response` | Consequência do `return False, "invalid_response"` na linha 91 |
| Pipeline final: `found=16 qualified=0` | Nenhum creator passou, filtro completamente ineficaz |

---

## Impacto

- O AI Filter **não está funcionando** — nenhum creator é aprovado ou reprovado com critério real.
- O custo OpenAI é cobrado (4 chamadas feitas), mas sem resultado útil.
- O critério customizado ("Aceite quem gosta de tattoo") nunca é avaliado de verdade.

---

## Correções necessárias

### Fix 1 — Corrigir o modelo (alta prioridade)
No arquivo de settings/env, alterar:
```
GPT_FILTER_MODEL=gpt-5-nano   # ← não existe
```
Para:
```
GPT_FILTER_MODEL=gpt-4o-mini  # ← correto
```

### Fix 2 — Separar system/user messages (recomendado)
Em `pipeline/ai_filter.py`, substituir a construção da chamada para usar `role: system` separado do `role: user`.

---

## Arquivo afetado

- `draper/pipeline/ai_filter.py` — linhas 63–72 (construção do prompt e chamada à API)
- Configuração de ambiente: variável `GPT_FILTER_MODEL`
