#!/bin/bash
set -e

apt update
apt install -y docker.io docker-compose-plugin nginx git certbot python3-certbot-nginx

systemctl enable docker
systemctl start docker

mkdir -p /opt/afilibot
cd /opt

git clone https://github.com/sangust/bot-telegram.git
cd bot-telegram/deploy

docker compose up -d

cp nginx.conf /etc/nginx/sites-available/bot-telegram
ln -s /etc/nginx/sites-available/bot-telegram /etc/nginx/sites-enabled/

nginx -t
systemctl restart nginx