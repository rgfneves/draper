# Google OAuth Setup para Draper

Draper agora usa **Google OAuth** para autenticação, restrito ao domínio `@worldpackers.com`.

---

## Passo 1: Criar Google OAuth App

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um novo projeto (ou use um existente)
3. Vá em **APIs & Services → Credentials**
4. Clique em **Create Credentials → OAuth 2.0 Client ID**
5. Selecione **Web application**
6. Preencha:
   - **Name**: `Draper Dashboard`
   - **Authorized JavaScript origins**: 
     - `https://draper-cxg5.onrender.com`
     - `http://localhost:8501` (para desenvolvimento local)
   - **Authorized redirect URIs**:
     - `https://draper-cxg5.onrender.com/`
     - `http://localhost:8501/`

   > ⚠️ O Streamlit não expõe rotas customizadas. O Google redireciona de volta para a raiz (`/`) com `?code=...` como query param — o app lê e processa automaticamente.

7. Clique em **Create**
8. Copie o **Client ID** e **Client Secret** — você vai usar no próximo passo

---

## Passo 2: Configurar Variáveis no Render

No dashboard do Render, vá em **Environment** e adicione:

| Variável | Valor |
|----------|-------|
| `GOOGLE_OAUTH_CLIENT_ID` | Client ID copiado acima |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Client Secret copiado acima |

---

## Passo 3: Deploy

1. Faça commit das mudanças:
   ```bash
   git add requirements.txt dashboard/app.py dashboard/auth.py
   git commit -m "feat: add Google OAuth authentication"
   git push origin main
   ```

2. O Render fará deploy automático
3. Acesse `https://draper.onrender.com`
4. Você será redirecionado para login com Google
5. Apenas emails `@worldpackers.com` terão acesso

---

## Desenvolvimento Local

Para testar localmente:

```bash
# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
export GOOGLE_OAUTH_CLIENT_ID="seu-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="seu-client-secret"
export DATABASE_URL="postgresql://..."
export APIFY_API_TOKEN="..."
export OPENAI_API_KEY="..."

# Rode o dashboard
streamlit run dashboard/app.py
```

Acesse `http://localhost:8501` e faça login com sua conta Google.

---

## Troubleshooting

### "GOOGLE_OAUTH_CLIENT_ID not set"
- Verifique se as variáveis foram adicionadas em **Environment** no Render
- Aguarde 1-2 minutos para o deploy atualizar
- Clique em **Manual Deploy → Deploy latest commit**

### "Email not authorized"
- Apenas `@worldpackers.com` tem acesso
- Contate tech@worldpackers.com para adicionar novos usuários

### Erro de redirect URI
- Verifique se a URL no Google Cloud Console bate com a do Render
- Para Render: `https://draper.onrender.com/auth/callback`
- Para local: `http://localhost:8501/auth/callback`

---

## Segurança

✅ **O que está protegido:**
- Apenas usuários `@worldpackers.com` acessam
- Tokens OAuth são verificados via Google
- Sessão armazenada no Streamlit session state (seguro)

⚠️ **Próximos passos (opcional):**
- Adicionar logging de acessos
- Implementar rate limiting
- Adicionar 2FA para contas críticas

