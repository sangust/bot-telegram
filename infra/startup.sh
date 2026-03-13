#!/bin/bash
set -euo pipefail

exec > >(tee -a /var/log/afilibot-startup.log) 2>&1

database_url_value="$(printf '%s\n' '${database_url}' | sed 's/^DATABASE_URL=//')"
secret_key_value='${secret_key}'
google_client_id_value='${google_client_id}'
google_client_secret_value='${google_client_secret}'
google_redirect_uri_value='${google_redirect_uri}'
mercadopago_access_token_value='${mercadopago_access_token}'
mercadopago_webhook_secret_value='${mercadopago_webhook_secret}'
base_url_value='${base_url}'
bot_token_1_value='${bot_token_1}'
bot_token_2_value='${bot_token_2}'
bot_token_3_value='${bot_token_3}'
dockerhub_username_value='${dockerhub_username}'
dockerhub_token_value='${dockerhub_token}'
db_password_value='${db_password}'
worker_count_value='${worker_count}'
docker_image="$dockerhub_username_value/afilibot:latest"
base_host="$(printf '%s\n' "$base_url_value" | sed -E 's#^[A-Za-z]+://([^/:]+).*$#\1#')"

if [ -z "$base_host" ]; then
  base_host="afilibot.shop"
fi

server_names="$base_host"
if [ "$base_host" = "afilibot.shop" ]; then
  server_names="afilibot.shop www.afilibot.shop"
fi

apt-get update -y
apt-get install -y nginx certbot python3-certbot-nginx curl ca-certificates

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

systemctl enable docker
systemctl start docker
systemctl enable nginx

for _ in $(seq 1 60); do
  if docker info >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! docker info >/dev/null 2>&1; then
  echo "docker não ficou disponível" >&2
  exit 1
fi

if ! docker ps -a --format '{{.Names}}' | grep -q '^afilibot_db$'; then
  docker run -d \
    --name afilibot_db \
    --restart always \
    -e POSTGRES_DB=afilibot \
    -e POSTGRES_USER=afilibot \
    -e POSTGRES_PASSWORD="$db_password_value" \
    -v postgres_data:/var/lib/postgresql/data \
    -p 5432:5432 \
    postgres:16-alpine
else
  docker start afilibot_db >/dev/null 2>&1 || true
fi

for _ in $(seq 1 60); do
  if docker exec afilibot_db pg_isready -U afilibot >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! docker exec afilibot_db pg_isready -U afilibot >/dev/null 2>&1; then
  echo "postgres não ficou saudável a tempo" >&2
  exit 1
fi

mkdir -p /opt/afilibot
cat > /opt/afilibot/.env <<EOF
DATABASE_URL="$database_url_value"
SECRET_KEY="$secret_key_value"
APP_ENV=production
GOOGLE_CLIENT_ID="$google_client_id_value"
GOOGLE_CLIENT_SECRET="$google_client_secret_value"
GOOGLE_REDIRECT_URI="$google_redirect_uri_value"
MERCADOPAGO_ACCESS_TOKEN="$mercadopago_access_token_value"
MERCADOPAGO_WEBHOOK_SECRET="$mercadopago_webhook_secret_value"
BASE_URL="$base_url_value"
BOT_TOKEN_1="$bot_token_1_value"
BOT_TOKEN_2="$bot_token_2_value"
BOT_TOKEN_3="$bot_token_3_value"
EOF
chmod 600 /opt/afilibot/.env

echo "$dockerhub_token_value" | docker login -u "$dockerhub_username_value" --password-stdin
docker pull "$docker_image"

docker rm -f afilibot-web afilibot-scraper >/dev/null 2>&1 || true
docker ps -a --format '{{.Names}}' | grep '^afilibot-worker-' | xargs -r docker rm -f >/dev/null 2>&1 || true

docker run --rm \
  --env-file /opt/afilibot/.env \
  --network host \
  -e APP_ROLE=migrate \
  "$docker_image" \
  python -m app.runtime

docker run -d \
  --name afilibot-web \
  --restart always \
  --network host \
  --env-file /opt/afilibot/.env \
  -e APP_ROLE=web \
  "$docker_image"

for worker_index in $(seq 1 "$worker_count_value"); do
  docker run -d \
    --name "afilibot-worker-$worker_index" \
    --restart always \
    --network host \
    --env-file /opt/afilibot/.env \
    -e APP_ROLE=worker \
    "$docker_image"
done

docker run -d \
  --name afilibot-scraper \
  --restart always \
  --network host \
  --env-file /opt/afilibot/.env \
  -e APP_ROLE=scraper \
  "$docker_image"

web_ready=0
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    web_ready=1
    break
  fi
  sleep 5
done

if [ "$web_ready" != "1" ]; then
  echo "afilibot web não ficou saudável a tempo" >&2
  docker ps -a || true
  docker logs afilibot-web || true
  exit 1
fi

cat > /etc/nginx/sites-available/afilibot <<EOF
server {
    listen 80;
    server_name $server_names;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/afilibot /etc/nginx/sites-enabled/afilibot
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl restart nginx

sleep 30

if printf '%s' "$base_host" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "certbot ignorado para host em formato de IP: $base_host"
elif [ "$base_host" = "afilibot.shop" ]; then
  certbot --nginx \
    --non-interactive \
    --agree-tos \
    --email admin@afilibot.shop \
    -d afilibot.shop \
    -d www.afilibot.shop || true
else
  certbot --nginx \
    --non-interactive \
    --agree-tos \
    --email admin@"$base_host" \
    -d "$base_host" || true
fi

systemctl enable certbot.timer
systemctl start certbot.timer