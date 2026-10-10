# /new-agent - Create a New Agent

Guides the user through creating a new agent skill file. See `docs/creating-agents.md` for the full reference.

## Steps

1. **Gather requirements.** Ask the user:
   - "What should this agent do?" (one sentence)
   - "Should it run on a schedule, or only when you run it or hand it a task?"
   - "Does it need to search the web?"

2. **Generate the skill file:**
   - Copy `backend/skills/_template.yaml` to `backend/skills/<slug>.yaml`. Don't start the filename with `_`, because those files are ignored.
   - Fill in `name`, `description`, `type` (marketing, research, content, ops or general), `persona` and `tone`. The slug used by `/run` and `/ask` comes from `name`.
   - Choose the model:
     - `claude-haiku-4-5` for scanning, classifying and simple tasks
     - `claude-sonnet-4-6` for research, analysis and writing
   - Grant only the tools it needs: `web_search`, `bash`, `write`.
   - Set `data.reads` from `projects`, `tasks`, `notes`, `leads` and `marketing_content`.
   - Set `data.writes` from `tasks` (this also covers leads), `notes` and `marketing_content`.
   - Set the schedule: `interval` (e.g. `every: 12h`), `cron` (e.g. `every: "0 9 * * *"`, read in `NOTIFICATION_TIMEZONE`), or `manual`.
   - Write a focused `prompt_template`:
     - Use `{{...}}` variables for the data it reads. Its memory and recent runs are appended automatically.
     - Spell out the JSON it must return: `summary`, plus `actions` using `create_task`, `update_task`, `create_note`, `create_lead`, `create_content` or `save_memory`.
   - Set `max_budget_usd`, `max_actions_per_run`, and `requires_approval: true` if its actions should wait for Approve/Reject on Telegram.

3. **Load it.** Skills are synced on backend startup:
   - Restart the backend: `docker compose restart backend`, or restart uvicorn.
   - Check that the agent appears: `curl -s http://localhost:8000/api/agents`.

4. **Test it:**
   - Preview the rendered prompt: `curl -s -X POST "http://localhost:8000/api/agents/<id>/run?dry_run=true"`
   - Do a real run with `curl -X POST http://localhost:8000/api/agents/<id>/run`, or `/run <slug>` on Telegram. Runs happen in the background, so poll `GET /api/agents/<id>/runs` for the result.
   - Show the user the summary and actions, and ask whether they want any adjustments.

## Guidelines

- One agent, one job. Don't make multi-purpose agents.
- Set `max_budget_usd` modestly, e.g. 0.10 for Haiku and 0.25-0.30 for Sonnet. It caps one run against the SDK's cost estimate.
- Use tags on the tasks, leads and notes the agent creates so they're easy to filter and dedupe.
- Any agent can also be handed tasks with `/ask <agent> <request>`, so a clear `description` matters. The chat uses it to pick an agent.
