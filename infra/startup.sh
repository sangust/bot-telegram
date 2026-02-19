#!/bin/bash
apt update
apt install -y docker.io
systemctl start docker
systemctl enable docker
sleep 15
docker pull santanex/afilibot
sleep 15
docker run -d -p 80:8000 --name afilibots santanex/afilibot