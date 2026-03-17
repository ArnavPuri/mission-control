FROM python:3.12-slim

WORKDIR /app

# Install system deps for psycopg2 and Claude Agent SDK
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI (bundled with Agent SDK, but good to have standalone)
RUN curl -fsSL https://claude.ai/install.sh | bash || true

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
