# afiliBot — SaaS de Bots de Promoções no Telegram

Plataforma para criar e operar bots de Telegram que monitoram lojas e categorias promocionais, aplicam links de afiliado e enviam alertas para grupos com execução previsível em produção.

---

## Como funciona

O fluxo operacional do projeto funciona assim:

```
Usuário configura o bot pela aplicação web
        ↓
Onboarding do Telegram gera uma conexão temporária persistida
        ↓
Configuração do bot salva lojas, links de afiliado e horários no PostgreSQL
        ↓
Worker agenda e consome jobs persistidos em delivery_jobs
        ↓
Bot envia promoções para o grupo no Telegram
```

---

## Funcionalidades

- **Scraping multi-plataforma:** integra com a API nativa do Shopify (`/products.json`) e faz web scraping de lojas Nuvemshop via BeautifulSoup
- **Detecção de desconto inteligente:** compara `price` vs `compare_at_price` de cada variante para identificar produtos realmente em promoção
- **Envio automático no Telegram:** foto do produto + marca, nome, tamanhos disponíveis, preço original vs atual e link direto
- **Links de afiliado por loja:** o bot pode usar link padrão e sobrescrita por store
- **Agendamento persistente:** horários ficam em `bot_schedules` e execuções em `delivery_jobs`
- **Onboarding estável do Telegram:** conexão do grupo é persistida em `pending_chat_ids`
- **Webhook estável por alias:** URLs públicas não expõem o token bruto do bot
- **Marketplace integrado:** categorias do Mercado Livre podem ser usadas como fontes válidas do bot
- **Aplicação web:** FastAPI + Jinja para onboarding, dashboard, autenticação e assinatura

---

## Stack

| Camada | Tecnologias |
|---|---|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL |
| **Scraping** | httpx, BeautifulSoup, Shopify API |
| **Bot** | python-telegram-bot |
| **Auth / Sessão** | Google OAuth, Starlette SessionMiddleware |
| **Pagamentos** | Mercado Pago (Checkout Pro + Webhook de payment) |
| **Infra** | Docker, Terraform, Azure VM, Nginx, Certbot, GitHub Actions |

---

## Arquitetura

```
app/
├── api/
│   ├── main.py              # FastAPI + healthcheck + sessões
│   └── routes/
│       ├── auth.py
│       ├── createbot.py     # Onboarding, webhook Telegram e setup do bot
│       ├── dashboard.py
│       └── subscription.py
├── runtime.py               # Entrypoint por papel: web, worker e migrate
├── src/
│   ├── domain/
│   │   └── models.py        # Bot, BotSchedule, DeliveryJob, PendingChatId
│   ├── infrabackend/
│   │   ├── config.py        # Ambiente, aliases de token e parâmetros operacionais
│   │   ├── database.py      # Engine SQLAlchemy e healthcheck do banco
│   │   ├── repository.py    # Repositórios do domínio e fila persistida
│   │   └── schemas.py
│   └── services/
│       ├── bot.py           # Lógica de envio Telegram
│       ├── delivery.py      # Scheduler, worker, webhook e onboarding persistido
│       ├── extract.py
│       └── mlExtract.py
app/data/alembic/
├── env.py
└── versions/
infra/
├── main.tf                  # Terraform da VM Azure
├── variables.tf
└── startup.sh               # Sobe banco, migrate, web, worker, Nginx e Certbot
```

---

## Lojas monitoradas

**Shopify (via API):** Mad Enlatados, New, Piet, Pace, Carnan, 1of1, EghoStudios, Sufgang, CienaLab, Anty, IceCompany e mais

**Nuvemshop (scraping):** Brunxind, Overstreets, Basyc, Captive Club, Malan, Places Wo, Delafoe, Street Apparel, YungCeo, TakeOff e mais

---

## Rodando localmente

**Pré-requisitos:** Python 3.12+, Poetry e PostgreSQL disponível.

**Variáveis mínimas de ambiente:**

```env
DATABASE_URL=postgresql+psycopg2://afilibot:senha@localhost:5432/afilibot
SECRET_KEY=uma_chave_forte
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
BASE_URL=http://localhost:8000
BOT_TOKEN_1=...
BOT_TOKEN_2=...
BOT_TOKEN_3=...
MERCADOPAGO_ACCESS_TOKEN=...
MERCADOPAGO_WEBHOOK_SECRET=...
MERCADOPAGO_API_URL=https://api.mercadopago.com
MERCADOPAGO_CURRENCY_ID=BRL
ML_PROXY_URLS=http://user:pass@host:port,http://user:pass@host2:port2
APP_ENV=development
APP_TIMEZONE=America/Sao_Paulo
```

**Subida local sugerida:**

```bash
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.api.main:app --reload
```

Para rodar o worker localmente:

```bash
APP_ROLE=worker poetry run python -m app.runtime
```

Para rodar um único ciclo do scraper localmente e ver logs no terminal:

```bash
poetry run python -m app.runtime scraper_once
```

Para rodar o scraper em loop:

```bash
poetry run python -m app.runtime scraper
```

Se você usar proxies no scraper do Mercado Livre, prefira informar `ML_PROXY_URLS` em linha única, separado por vírgula. Se deixar vazio, o scraper tenta conexão direta primeiro.

---

## Pagamentos com Mercado Pago

O checkout de assinatura usa o Mercado Pago em modo hospedado (`Checkout Pro`) e retorna `payment_url` para o frontend.

O estado recorrente da assinatura continua sendo controlado no banco local:

- `subscriptions` guarda o estado atual da assinatura
- `payments` guarda o histórico das cobranças confirmadas
- `next_payment` é calculado localmente após um pagamento aprovado

O webhook processa notificações do tipo `payment`, consulta `GET /v1/payments/{id}` no Mercado Pago e sincroniza:

- `pending`
- `active`
- `canceled`

O método de pagamento é inferido do pagamento confirmado:

- `PIX`
- `CARD`

---

## Configurando o webhook do Mercado Pago

### 1. Criar as credenciais

No painel do Mercado Pago, obtenha:

- `MERCADOPAGO_ACCESS_TOKEN`
- a chave secreta gerada na configuração do webhook, que deve ser salva em `MERCADOPAGO_WEBHOOK_SECRET`

### 2. Configurar a URL do webhook

No painel **Your integrations** do Mercado Pago:

- abra a aplicação usada no Checkout Pro
- vá em **Webhooks**
- configure a URL HTTPS pública da aplicação

Exemplo:

```text
https://SEU_DOMINIO/api/subscription/webhook
```

### 3. Selecionar o evento correto

Configure o evento:

```text
Payments
```

O payload esperado pelo backend segue o formato de notificação de `payment`, com `data.id` e `type=payment`.

### 4. Salvar a secret do webhook

Ao salvar a configuração, o Mercado Pago gera uma secret exclusiva do webhook. Salve essa secret em:

```env
MERCADOPAGO_WEBHOOK_SECRET=...
```

O backend valida a assinatura recebida pelos headers `x-signature` e `x-request-id`.

### 5. Simular a notificação

No próprio painel do Mercado Pago:

- use a opção **Simulate**
- selecione a URL configurada
- escolha o evento **Payments**
- envie um `Data ID` de teste

O endpoint deve responder com `200` ou `201`.

### 6. Requisitos para ambiente local

Para testar webhook localmente, você precisa expor a aplicação por uma URL HTTPS pública, por exemplo com túnel.

Depois disso, use essa URL pública tanto em:

- `BASE_URL`
- configuração do webhook no painel do Mercado Pago

---

## Deploy

### Docker

```bash
docker build -t afilibot .
docker run --rm --env-file .env -e APP_ROLE=migrate afilibot
docker run -d --env-file .env -e APP_ROLE=web -p 8000:8000 afilibot
docker run -d --env-file .env -e APP_ROLE=worker afilibot
```

A mesma imagem suporta três papéis:

- **`migrate`**
- **`web`**
- **`worker`**

### Azure com Terraform

```bash
terraform init
terraform apply
```

A infraestrutura sobe uma VM Linux com Docker, Postgres, Nginx e Certbot. O `startup.sh` executa migrations antes de iniciar `web` e `worker`.

---

## CI/CD

O workflow `envios.yml` roda via GitHub Actions:

- **Trigger:** execução manual
- **Build:** login no Docker Hub, build da imagem e push da tag `latest`
- **Deploy:** `terraform apply` com secrets de Azure, banco, OAuth, Mercado Pago e bots do Telegram
- **Resultado:** a VM baixa a imagem nova, executa migration e sobe `web` + `worker`

---

## Autor

**Gustavo Santana** — [linkedin.com/in/zssantana](https://linkedin.com/in/zssantana)
