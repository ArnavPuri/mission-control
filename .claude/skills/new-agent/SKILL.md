# /new-agent - Create a New Agent

Guides the user through creating a new agent skill file.

## Steps

1. **Gather requirements**:
   - Ask: "What should this agent do?" (one sentence description)
   - Ask: "What type?" (marketing, research, content, ops)
   - Ask: "Should it run on a schedule or manually?"
   - Ask: "Which project is it for?" (or none)

2. **Generate the skill file**:
   - Copy `backend/skills/_template.yaml`
   - Fill in name, description, type
   - Choose the right model:
     - Haiku for scanning, classifying, simple tasks
     - Sonnet for analysis, strategy, complex writing
   - Set appropriate data reads/writes based on what it needs
   - Write a focused prompt template
   - Set a reasonable budget cap

3. **Save and sync**:
   - Save to `backend/skills/<slug>.yaml`
   - Call the backend to reload skills (or restart)
   - Verify the agent appears in the API: `curl http://localhost:8000/api/agents`

4. **Test**:
   - Trigger a manual run: `curl -X POST http://localhost:8000/api/agents/<id>/run`
   - Show the results
   - Ask if adjustments are needed

## Guidelines

- One agent, one job. Don't make multi-purpose agents.
- Always set max_budget_usd (default: $0.10 for Haiku, $0.30 for Sonnet)
- Keep prompt templates focused and include the expected JSON output format.
- Use tags in created tasks/ideas so the dashboard can filter by source.
