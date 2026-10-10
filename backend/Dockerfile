FROM python:3.12-slim-trixie

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# git/curl for agents with shell access; postgresql-client (pg_dump 17, which
# can back up the Postgres 16 server) for nightly backups
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first so code changes don't reinstall them
COPY pyproject.toml .
RUN mkdir app && touch app/__init__.py && pip install -e . && rm -rf app

COPY . .

# The Claude CLI ships inside claude-agent-sdk; no separate install needed
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
