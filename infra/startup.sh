#!/bin/bash
set -e

# Atualiza pacotes e instala dependências
apt update
apt install -y ca-certificates curl gnupg git nginx certbot python3-certbot-nginx

# Adiciona a chave oficial do Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Adiciona o repositório oficial do Docker
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instala o Docker e o plugin Compose v2
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker

# Prepara o diretório e clona o projeto diretamente na pasta correta
mkdir -p /opt/afilibot
cd /opt/afilibot

git clone https://github.com/sangust/bot-telegram.git .

# Configura o Nginx
cp deploy/nginx.conf /etc/nginx/sites-available/bot-telegram
ln -sf /etc/nginx/sites-available/bot-telegram /etc/nginx/sites-enabled/

nginx -t
systemctl restart nginx