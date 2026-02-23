#!/bin/bash
set -e

# ── Instala Docker ─────────────────────────────────────────────────────────────
apt-get update -y
curl -fsSL https://get.docker.com | sh
systemctl start docker
systemctl enable docker

# ── Aguarda Docker inicializar ─────────────────────────────────────────────────
sleep 10

# ── Sobe o Postgres ────────────────────────────────────────────────────────────
docker run -d \
  --name afilibot_db \
  --restart always \
  -e POSTGRES_DB=afilibot \
  -e POSTGRES_USER=afilibot \
  -e POSTGRES_PASSWORD=${db_password} \
  -v postgres_data:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:16-alpine

# Aguarda o banco ficar pronto
sleep 20

# ── Cria o .env ────────────────────────────────────────────────────────────────
mkdir -p /opt/afilibot
cat > /opt/afilibot/.env << EOF
DATABASE_URL=${database_url}
SECRET_KEY=${secret_key}
GOOGLE_CLIENT_ID=${google_client_id}
GOOGLE_CLIENT_SECRET=${google_client_secret}
GOOGLE_REDIRECT_URI=${google_redirect_uri}
ABACATEPAY_API_KEY=${abacatepay_api_key}
ABACATEPAY_API_URL=${abacatepay_api_url}
ABACATEPAY_WEBHOOK_SECRET=${abacatepay_webhook_secret}
BASE_URL=${base_url}
BOT_TOKEN_1=${bot_token_1}
BOT_TOKEN_2=${bot_token_2}
BOT_TOKEN_3=${bot_token_3}
EOF

# ── Login Docker Hub e pull da imagem ──────────────────────────────────────────
echo "${dockerhub_token}" | docker login -u "${dockerhub_username}" --password-stdin
docker pull ${dockerhub_username}/afilibot:latest

# ── Migrations ────────────────────────────────────────────────────────────────
docker run --rm \
  --env-file /opt/afilibot/.env \
  --network host \
  ${dockerhub_username}/afilibot:latest \
  alembic upgrade head

# ── Sobe o app ────────────────────────────────────────────────────────────────
docker run -d \
  --name afilibot \
  --restart always \
  --network host \
  --env-file /opt/afilibot/.env \
  -p 80:8000 \
  ${dockerhub_username}/afilibot:latest
