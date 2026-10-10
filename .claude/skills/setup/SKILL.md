# /setup - Mission Control Onboarding

Run the initial Mission Control setup. This guides the user through auth, Telegram, the database, and optional integrations, then starts the app.

`./setup.sh` is an interactive version of steps 2-5. Offer it if the user would rather answer prompts in a terminal.

## Steps

1. **Check prerequisites.** Docker with Docker Compose is enough to run everything. Python 3.11+ and Node 20+ are only needed for local development without Docker. If anything is missing, offer to install it.

2. **Create `.env`.** Copy it from `.env.example` if it doesn't exist.

3. **Configure authentication** (required):
   - Mission Control runs on a Claude Pro/Max subscription. It doesn't use an API key.
   - Tell the user to run `claude setup-token` (or `claude auth login`) and put the token in `.env` as `CLAUDE_CODE_OAUTH_TOKEN`.

4. **Configure Telegram** (required, because Telegram is the main interface):
   - Walk the user through creating a bot with @BotFather, then set `TELEGRAM_BOT_TOKEN`.
   - Set `TELEGRAM_ALLOWED_USERS` to their numeric Telegram user ID. They can get it from @userinfobot. If they message the bot before the ID is set, it replies with their ID. The bot ignores everyone not on the list.
   - Ask for their timezone and set `NOTIFICATION_TIMEZONE` (e.g. `Europe/Berlin`). It controls when the 8:00 morning briefing goes out and how agent cron schedules are read.

5. **Choose the database:**
   - PostgreSQL (default) uses `docker compose up -d`.
   - SQLite uses `USE_SQLITE=true` and `docker compose -f docker-compose.sqlite.yml up -d`.

6. **Optional integrations:**
   - `GITHUB_TOKEN` (Issues read/write) enables `/dev`, which hands coding work to Claude Code through GitHub issues. Remind the user to install the Claude GitHub app (https://github.com/apps/claude) on their repos.
   - `OPENAI_API_KEY` enables transcription of Telegram voice messages.

7. **Start services:**
   - Run the compose command for the chosen database. It starts the database (unless using SQLite), the backend and the dashboard. Migrations run automatically on startup.
   - Wait for `curl -sf http://localhost:8000/health` to report `"status": "ok"`.

8. **Load initial data:**
   - Ask: "What are your current projects?" Create each one with `POST /api/projects`, including `github_repo` ("owner/repo") if they want to use `/dev` for it.
   - Offer to fill in `workspace/identity.md`, a short "about me" that every agent and the chat see.
   - Offer to set up the brand profile (dashboard → Settings) if they want the marketing agents.
   - Show the available agents (`GET /api/agents`) and their schedules. Ask whether any should be switched to manual or disabled.

9. **Verify everything:**
   - Open http://localhost:3000.
   - Ask the user to send `/status` to the bot, then try `/ask ace <something>` to see the delegation flow.

## Important

- Don't collect tokens or keys in this chat. Ask the user to write them to `.env` directly, or write them there yourself if they paste them.
- If something fails, diagnose and fix it. Don't ask the user to fix things manually.
