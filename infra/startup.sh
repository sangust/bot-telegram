#!/bin/bash
set -e

apt-get update -y
apt-get install -y nginx certbot python3-certbot-nginx

curl -fsSL https://get.docker.com | sh
systemctl start docker
systemctl enable docker

until docker info >/dev/null 2>&1; do
  sleep 2
done

sleep 10

if ! docker ps -a --format '{{.Names}}' | grep -q '^afilibot_db$'; then
  docker run -d \
    --name afilibot_db \
    --restart always \
    -e POSTGRES_DB=afilibot \
    -e POSTGRES_USER=afilibot \
    -e POSTGRES_PASSWORD="${db_password}" \
    -v postgres_data:/var/lib/postgresql/data \
    -p 5432:5432 \
    postgres:16-alpine
else
  docker start afilibot_db >/dev/null 2>&1 || true
fi

sleep 20

mkdir -p /opt/afilibot
cat > /opt/afilibot/.env <<EOF
DATABASE_URL="${database_url}"
SECRET_KEY="${secret_key}"
APP_ENV=production
GOOGLE_CLIENT_ID="${google_client_id}"
GOOGLE_CLIENT_SECRET="${google_client_secret}"
GOOGLE_REDIRECT_URI="${google_redirect_uri}"
MERCADOPAGO_ACCESS_TOKEN="${mercadopago_access_token}"
MERCADOPAGO_WEBHOOK_SECRET="${mercadopago_webhook_secret}"
BASE_URL="${base_url}"
BOT_TOKEN_1="${bot_token_1}"
BOT_TOKEN_2="${bot_token_2}"
BOT_TOKEN_3="${bot_token_3}"
EOF

echo "${dockerhub_token}" | docker login -u "${dockerhub_username}" --password-stdin
docker pull ${dockerhub_username}/afilibot:latest

docker rm -f afilibot afilibot-web afilibot-worker afilibot-scraper >/dev/null 2>&1 || true
docker ps -a --format '{{.Names}}' | grep '^afilibot-worker-' | xargs -r docker rm -f >/dev/null 2>&1 || true

docker run --rm \
  --env-file /opt/afilibot/.env \
  --network host \
  -e APP_ROLE=migrate \
  ${dockerhub_username}/afilibot:latest \
  python -m app.runtime

docker run -d \
  --name afilibot-web \
  --restart always \
  --network host \
  --env-file /opt/afilibot/.env \
  -e APP_ROLE=web \
  ${dockerhub_username}/afilibot:latest

for worker_index in $(seq 1 ${worker_count}); do
  docker run -d \
    --name afilibot-worker-${worker_index} \
    --restart always \
    --network host \
    --env-file /opt/afilibot/.env \
    -e APP_ROLE=worker \
    ${dockerhub_username}/afilibot:latest
done

docker run -d \
  --name afilibot-scraper \
  --restart always \
  --network host \
  --env-file /opt/afilibot/.env \
  -e APP_ROLE=scraper \
  ${dockerhub_username}/afilibot:latest

web_ready=0
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    web_ready=1
    break
  fi
  sleep 5
done

if [ "$web_ready" != "1" ]; then
  echo "afilibot web não ficou saudável a tempo" >&2
  exit 1
fi

cat > /etc/nginx/sites-available/afilibot << 'NGINXEOF'
server {
    listen 80;
    server_name afilibot.shop www.afilibot.shop;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
NGINXEOF

ln -sf /etc/nginx/sites-available/afilibot /etc/nginx/sites-enabled/afilibot
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl restart nginx

sleep 30

certbot --nginx \
  --non-interactive \
  --agree-tos \
  --email admin@afilibot.shop \
  -d afilibot.shop \
  -d www.afilibot.shop

systemctl enable certbot.timer
systemctl start certbot.timer