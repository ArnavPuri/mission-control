# /setup - Mission Control Onboarding

Run the initial Mission Control setup. Guides through auth configuration,
database setup, and optional integrations.

## Steps

1. **Check prerequisites**: Ensure Docker, Python 3.11+, and Node 20+ are installed.
   If missing, offer to install them.

2. **Configure authentication**:
   - Ask: "How would you like to authenticate with Claude?"
     - **API Key** (recommended): Ask user to paste their ANTHROPIC_API_KEY
     - **Claude Subscription** (Pro/Max): Tell user to run `claude setup-token` in another terminal, then paste CLAUDE_CODE_OAUTH_TOKEN
     - **OpenRouter**: Ask for OPENROUTER_API_KEY
     - **Ollama (local)**: Ask for OLLAMA_BASE_URL (default: http://localhost:11434)
   - Write the chosen credentials to `.env` (copy from `.env.example` first)

3. **Configure Telegram (optional)**:
   - Ask: "Do you want to add items via Telegram?"
   - If yes: Guide through @BotFather bot creation, collect TELEGRAM_BOT_TOKEN
   - Ask for TELEGRAM_ALLOWED_USERS (their Telegram user ID)

4. **Start services**:
   - Run `docker compose up -d` to start Postgres and Redis
   - Wait for health checks to pass
   - Run `cd backend && pip install -e ".[dev]"` for local dev
   - Run `cd backend && uvicorn app.main:app --reload` to start the backend
   - Verify with `curl http://localhost:8000/health`

5. **Load initial data**:
   - Ask: "What are your current projects?" and create them via API
   - Ask: "Any agents you want to enable right away?" and show available skills

6. **Dashboard setup**:
   - Run `cd dashboard && npm install && npm run dev`
   - Open http://localhost:3000

7. **Verify everything**:
   - Check health endpoint
   - If Telegram configured, send /status to the bot
   - Show the user their running setup

## Important

- Do NOT collect API keys or tokens in this chat. Always write them to `.env` directly.
- If something fails, diagnose and fix it. Don't ask the user to fix things manually.
- Create `.env` from `.env.example` if it doesn't exist.
