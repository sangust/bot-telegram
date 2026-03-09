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
| **Pagamentos** | AbacatePay |
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
ABACATEPAY_API_KEY=...
ABACATEPAY_API_URL=https://api.abacatepay.com/v1
ABACATEPAY_WEBHOOK_SECRET=...
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
- **Deploy:** `terraform apply` com secrets de Azure, banco, OAuth, pagamento e bots do Telegram
- **Resultado:** a VM baixa a imagem nova, executa migration e sobe `web` + `worker`

---

## Autor

**Gustavo Santana** — [linkedin.com/in/zssantana](https://linkedin.com/in/zssantana)
