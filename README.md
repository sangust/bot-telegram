# afiliBot — Alertas de Promoções de Streetwear no Telegram

Bot automatizado que monitora mais de **25 lojas de streetwear brasileiras**, detecta produtos em promoção e envia alertas diários direto no Telegram — com foto, preço original, preço atual e link.

---

## Como funciona

O pipeline roda automaticamente todo dia via GitHub Actions:

```
Coleta de produtos (Shopify API + Web Scraping)
        ↓
Normalização e detecção de desconto
        ↓
Sincronização com Google BigQuery (cloud)
        ↓
Envio das promoções via Telegram Bot
```

---

## Funcionalidades

- **Scraping multi-plataforma:** integra com a API nativa do Shopify (`/products.json`) e faz web scraping de lojas Nuvemshop via BeautifulSoup
- **Detecção de desconto inteligente:** compara `price` vs `compare_at_price` de cada variante para identificar produtos realmente em promoção
- **Envio automático no Telegram:** foto do produto + marca, nome, tamanhos disponíveis, preço original vs atual e link direto
- **Persistência local + cloud:** SQLite para controle local, BigQuery para histórico e análise
- **Pipeline diário automatizado:** GitHub Actions com `cron` roda todo dia à meia-noite, sem intervenção manual
- **Landing page:** interface web em FastAPI para visualização dos produtos monitorados

---

## Stack

| Camada | Tecnologias |
|---|---|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy, SQLite |
| **Scraping** | httpx, BeautifulSoup, Shopify API |
| **Bot** | python-telegram-bot |
| **Cloud / Dados** | Google BigQuery, GCP Compute Engine, pandas |
| **Infra** | Docker, Terraform, GitHub Actions (CI/CD) |

---

## Arquitetura

```
app/
├── main.py                  # Entrypoint — orquestra extração, sync e envio
├── api/                     # FastAPI — landing page de produtos
│   └── routes/
├── src/
│   ├── domain/
│   │   └── models.py        # Modelo ORM (SQLAlchemy)
│   ├── infrabackend/
│   │   ├── config.py        # URLs das lojas monitoradas
│   │   ├── database.py      # Conexão SQLite
│   │   ├── repository.py    # Repositórios local e cloud (BigQuery)
│   │   └── schemas.py       # Schema Pydantic para validação
│   └── services/
│       ├── bot.py           # Lógica de envio Telegram
│       └── extract.py       # Extração Shopify + Nuvemshop
infra/
├── main.tf                  # Terraform — VM no GCP (e2-micro, Debian 12)
├── variables.tf
└── startup.sh
```

---

## Lojas monitoradas

**Shopify (via API):** Mad Enlatados, New, Piet, Pace, Carnan, 1of1, EghoStudios, Sufgang, CienaLab, Anty, IceCompany e mais

**Nuvemshop (scraping):** Brunxind, Overstreets, Basyc, Captive Club, Malan, Places Wo, Delafoe, Street Apparel, YungCeo, TakeOff e mais

---

## Rodando localmente

**Pré-requisitos:** Python 3.12+, Poetry, conta GCP com BigQuery habilitado

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/bot-telegram-development
cd bot-telegram-development

# Instale as dependências
poetry install

# Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com seus tokens
```

**.env necessário:**
```env
BOT_TOKEN=seu_token_do_botfather
CHAT_ID=id_do_seu_canal_ou_grupo
```

```bash
# Execute o pipeline completo
poetry run python -m app.main

# Ou suba a API
poetry run uvicorn app.api.main:app --reload
```

---

## Deploy

### Docker

```bash
docker build -t garimpo-bot .
docker run --env-file .env garimpo-bot
```

### GCP com Terraform

```bash
cd infra
# Adicione credentials.json da sua service account GCP
terraform init
terraform apply
```

A VM é criada automaticamente no GCP (e2-micro) com firewall configurado nas portas 80 e 8000.

---

## CI/CD

O workflow `envios.yml` roda via GitHub Actions:

- **Trigger:** push na `main` ou automaticamente todo dia às 00:00 (UTC) via cron
- **Secrets necessários:** `BOT_TOKEN`, `CHAT_ID`, `GCP_SA_KEY`
- Após execução, o banco SQLite local é atualizado e commitado automaticamente

---

## Autor

**Gustavo Santana** — [linkedin.com/in/zssantana](https://linkedin.com/in/zssantana)
