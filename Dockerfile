FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ROLE=web

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    procps \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

# Dependências primeiro — aproveita cache do Docker
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

# Código da aplicação
COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD sh -c 'if [ "$APP_ROLE" = "worker" ]; then pgrep -f "python -m app.runtime" >/dev/null; else curl -fsS http://127.0.0.1:8000/health >/dev/null; fi' || exit 1

CMD ["python", "-m", "app.runtime"]