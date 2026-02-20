#!/bin/bash
apt update
apt install -y docker.io
systemctl start docker
systemctl enable docker
sleep 15
echo "dckr_pat_upxJvftheb_3l-nXjp07ZUTGDiQ" | docker login -u santanex --password-stdin
docker pull santanex/afilibot:latest
docker run -d -p 80:8000 --name afilibots santanex/afilibot