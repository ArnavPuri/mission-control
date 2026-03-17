# Mission Control Roadmap

> **Vision:** Make Mission Control the open-source personal AI command center that
> helps anyone harness AI agents for personal productivity — organizing life,
> work, learning, and side projects from a single pane of glass.

---

## Current State (v0.3)

What's already built:

- **Core data model** — Projects, tasks, ideas, reading list with full CRUD
- **Agent system** — YAML-defined skills, scheduled execution, Claude Agent SDK
- **9 agents** — Reddit Scout, Idea Validator, Weekly Prioritizer, Feedback Collector, Daily Check-in, Goal Decomposer, Evening Reflection, Weekly Review + template
- **Dashboard** — Light-theme Radix UI dashboard with cards, tooltips, popovers, progress bars, activity heatmap
- **Telegram bot** — 11 commands + natural language chat with LLM
- **MCP server** — 17 tools for Claude Code integration
- **Multi-auth** — API key, OAuth, OpenRouter, Ollama support
- **Event log** — Full audit trail of every system action
- **Habits system** — Track daily/weekly habits with streak tracking
- **Goals & OKRs** — Goals with measurable key results and Radix progress bars
- **Journal** — Daily entries with mood, energy, wins, challenges, gratitude
- **Agent approval queue** — Human-in-the-loop review before agent actions execute
- **Agent chaining** — Output of one agent feeds into the next via `chain_to`
- **Agent dry-run** — Preview actions without executing
- **Cross-entity search** — Search across all 7 data types + command palette (Cmd+K)
- **Webhook system** — Inbound (HMAC-verified) + outbound event dispatch + logs
- **Data export** — JSON (all entities) and CSV (per entity) downloads
- **Notification center** — In-app bell with unread count, mark read/all
- **Activity heatmap** — GitHub-style 12-week contribution graph with tooltips
- **Agent cost tracking** — Per-agent spending dashboard

---

## Progress Summary

| Phase | Done | Total | Progress |
|-------|------|-------|----------|
| 1. Foundation Hardening | 3 | 15 | 20% |
| 2. Intelligence Layer | 3 | 13 | 23% |
| 3. Personal Productivity | 10 | 23 | 43% |
| 4. Dashboard 2.0 | 10 | 18 | 56% |
| 5. Integrations | 4 | 18 | 22% |
| 6. Multi-Agent Intelligence | 0 | 16 | 0% |
| 7. Privacy & Scale | 0 | 16 | 0% |
| 8. Mobile & Desktop | 0 | 10 | 0% |
| 9. Community | 0 | 16 | 0% |
| **Total** | **30** | **145** | **21%** |

---

## Phase 1: Foundation Hardening

_Make what exists rock-solid and easy to set up._

### 1.1 Setup & Onboarding
- [ ] One-command install script (`curl | bash` or `npx create-mission-control`)
- [ ] Interactive setup wizard that walks through DB, auth, and Telegram config
- [ ] Pre-built Docker images on GitHub Container Registry (no local build needed)
- [ ] `.env` generator with validation and provider health checks
- [ ] SQLite mode for zero-config local development (no Postgres required)

### 1.2 Database & Migrations
- [ ] Alembic migration pipeline (currently uses auto-create on startup)
- [ ] Seed data with example projects, tasks, and ideas for new users
- [ ] Database backup/restore commands (`mc backup`, `mc restore`)
- [x] Data export to JSON/CSV for portability

### 1.3 Testing & Reliability
- [ ] Backend test suite (pytest) with CI pipeline
- [ ] Dashboard test suite (Vitest + React Testing Library)
- [x] Agent dry-run mode (preview actions without executing)
- [ ] Health check improvements: detailed diagnostics per component
- [ ] Graceful error handling for all LLM provider failures

### 1.4 Agent Robustness
- [x] Agent approval queue — human-in-the-loop before actions execute
- [ ] Retry logic with exponential backoff for transient LLM failures
- [ ] Agent timeout enforcement (kill stuck runs)
- [ ] Output validation — reject malformed agent responses gracefully
- [ ] Agent versioning — track skill file changes over time

---

## Phase 2: Intelligence Layer

_Make agents smarter and the system more context-aware._

### 2.1 Semantic Search & Memory
- [ ] pgvector embeddings on tasks, ideas, and reading items
- [x] Semantic search API (`/api/search?q=...`) across all entities
- [x] Dashboard search bar with instant results
- [ ] Agent memory — long-term context that persists across runs
- [ ] Deduplication: detect near-duplicate tasks and ideas before creating them

### 2.2 Smarter Agents
- [x] Agent chaining — output of one agent feeds into another
- [ ] Conditional triggers — run agent when specific DB conditions are met
- [ ] Agent-to-agent communication via shared context
- [ ] Multi-step agent workflows (DAGs) with dependency resolution
- [ ] Agent self-evaluation — score own output quality, retry if low confidence

### 2.3 Context Engine
- [ ] Auto-tag tasks and ideas using LLM classification
- [ ] Smart prioritization — ML-based priority suggestions from patterns
- [ ] Project health scoring — aggregate metrics per project
- [ ] Time-based context — "morning brief" vs "evening review" agent behavior
- [ ] User pattern learning — adapt agent schedules to user activity

---

## Phase 3: Personal Productivity Suite

_Go beyond task management into a full life operating system._

### 3.1 Habits & Routines
- [x] Habits table — recurring behaviors with streak tracking
- [x] Daily check-in agent — asks about habit completion, logs streaks
- [ ] Routine builder — morning/evening routines as checklists
- [x] Habit analytics — streaks, completion rates, weekly bar charts, trends

### 3.2 Goals & OKRs
- [x] Goals table — long-term objectives linked to projects
- [x] Key results with measurable targets and progress tracking
- [x] Goal decomposition agent — breaks goals into actionable tasks
- [x] Weekly/monthly goal review agent with progress reports
- [x] Goal visualization on dashboard (progress bars via Radix UI)

### 3.3 Journal & Reflection
- [x] Journal entries table — daily notes, reflections, wins
- [x] Daily reflection agent — prompts end-of-day review, generates insights
- [x] Weekly summary agent — synthesizes the week's activity into a report
- [x] Mood/energy tracking with optional daily check-in
- [ ] Journal search with semantic similarity

### 3.4 Calendar & Time
- [ ] Calendar integration (Google Calendar, CalDAV)
- [ ] Time blocking — schedule tasks into calendar slots
- [ ] Daily agenda agent — morning briefing with today's priorities
- [ ] Meeting prep agent — gathers context before calendar events
- [ ] Deadline awareness — agents factor in due dates for prioritization

### 3.5 Knowledge Management
- [ ] Notes table — long-form content with markdown support
- [ ] Auto-summarize reading list articles when marked as read
- [ ] Spaced repetition for learning items (Anki-style)
- [ ] Web clipper (browser extension) to save articles to reading list
- [ ] YouTube/podcast transcript ingestion and summarization
- [ ] RSS feed integration — auto-populate reading list from subscriptions

### 3.6 Finance Tracking (Lightweight)
- [ ] Simple income/expense logging
- [ ] Subscription tracker with renewal reminders
- [ ] Budget agent — weekly spending summary and alerts
- [ ] Financial goal tracking linked to goals system

---

## Phase 4: Dashboard 2.0

_Transform the dashboard from a status board into a powerful daily driver._

### 4.1 Core UX
- [x] Radix UI component library with clean light theme
- [x] Lucide icons throughout (replacing unicode)
- [ ] Multi-page layout: Dashboard, Projects, Agents, Journal, Settings
- [x] Mobile-responsive design (usable on phone)
- [x] Dark mode / light mode toggle with localStorage persistence
- [ ] Keyboard shortcuts for power users (vim-style navigation)
- [ ] Drag-and-drop task reordering and project assignment

### 4.2 Views & Visualizations
- [ ] Kanban board view for tasks (by status columns)
- [ ] Calendar view for tasks with due dates
- [ ] Timeline/Gantt view for project planning
- [x] Agent cost dashboard — spending per agent, per day, cumulative
- [x] Activity heatmap (GitHub-style contribution graph)
- [ ] Project dashboards — dedicated view per project with all related items

### 4.3 Interactivity
- [x] Inline task editing (double-click to edit text, click priority dot to change)
- [ ] Bulk actions — select multiple tasks, bulk update status/priority
- [ ] Quick capture — global keyboard shortcut to add task/idea/reading
- [x] Filters and saved views (filter tasks by status and priority with Radix dropdowns)
- [x] Command palette (Cmd+K) for fast navigation and actions

### 4.4 Notifications & Alerts
- [x] In-app notification center for agent completions and alerts
- [ ] Browser push notifications for critical events
- [ ] Daily digest email (optional)
- [ ] Customizable alert rules (e.g., "notify me when any critical task is created")

---

## Phase 5: Integrations Ecosystem

_Connect Mission Control to the tools people already use._

### 5.1 Input Channels
- [ ] Email ingestion — forward emails to create tasks/ideas
- [ ] WhatsApp bot (via WhatsApp Business API)
- [ ] Discord bot
- [ ] Slack bot
- [ ] Voice input via Telegram voice messages (whisper transcription)
- [ ] iOS/Android shortcut for quick capture
- [ ] Apple Shortcuts / Siri integration

### 5.2 Service Integrations
- [ ] GitHub — sync issues, PRs, notifications; auto-create tasks from issues
- [ ] Linear — bidirectional task sync
- [ ] Notion — import/export pages and databases
- [ ] Google Workspace — Docs, Sheets, Calendar
- [ ] Stripe — revenue alerts, subscription events
- [ ] Todoist / TickTick — bidirectional task sync for existing users
- [ ] Zapier/Make webhook endpoint for connecting anything

### 5.3 Webhook System
- [x] Inbound webhooks — generic endpoint that agents can process
- [x] Outbound webhooks — notify external services on events
- [ ] Webhook templates for common services
- [x] Webhook log with replay capability

### 5.4 API & Developer Platform
- [ ] Public REST API with API key authentication
- [ ] API rate limiting and usage tracking
- [x] OpenAPI/Swagger documentation auto-generated
- [ ] SDK packages (Python, TypeScript) for programmatic access
- [ ] Plugin system — community-contributed agents and integrations

---

## Phase 6: Multi-Agent Intelligence

_Build a team of specialized AI agents that collaborate._

### 6.1 Agent Marketplace
- [ ] Community agent gallery — browse and install skill files
- [ ] One-click agent installation from gallery
- [ ] Agent ratings and reviews
- [ ] Agent categories: productivity, marketing, research, health, finance, learning

### 6.2 Advanced Agent Capabilities
- [ ] Web browsing agent — research topics and summarize findings
- [ ] Code review agent — review PRs and suggest improvements
- [ ] Content creation agent — draft blog posts, tweets, newsletters
- [ ] Competitor monitoring agent — track competitor changes and news
- [ ] Opportunity scout agent — find freelance gigs, speaking opportunities
- [ ] Learning path agent — curate learning resources for a skill
- [ ] Health check-in agent — daily wellness prompts and tracking

### 6.3 Agent Orchestration
- [ ] Pipeline builder — visual editor for multi-agent workflows
- [ ] Event-driven triggers (not just schedules)
- [ ] Agent performance analytics — success rate, cost efficiency, action quality
- [ ] A/B testing for agent prompts — compare prompt variants
- [ ] Agent budget management dashboard with alerts

---

## Phase 7: Privacy, Security & Scale

_Make it production-grade and trustworthy._

### 7.1 Authentication & Multi-User
- [ ] User authentication (email/password, OAuth)
- [ ] Multi-user support with separate workspaces
- [ ] Role-based access control (admin, editor, viewer)
- [ ] Shared projects with team members
- [ ] Audit log per user

### 7.2 Privacy & Data Control
- [ ] End-to-end encryption for sensitive data fields
- [ ] Local-only mode — all LLM inference via Ollama, no data leaves device
- [ ] Data retention policies — auto-archive old items
- [ ] GDPR-compliant data export and deletion
- [ ] Prompt anonymization — strip PII before sending to LLM

### 7.3 Deployment & Scale
- [ ] Helm chart for Kubernetes deployment
- [ ] One-click deploy to Railway, Render, Fly.io
- [ ] Horizontal scaling with Redis-based task queue
- [ ] CDN and caching for dashboard assets
- [ ] Monitoring and alerting (Prometheus/Grafana)
- [ ] Automated database backups to S3-compatible storage

---

## Phase 8: Mobile & Desktop

_Meet users where they are._

### 8.1 Mobile App
- [ ] React Native or PWA mobile app
- [ ] Push notifications for agent completions and reminders
- [ ] Quick capture widget (home screen shortcut)
- [ ] Offline mode with sync when back online
- [ ] Voice input for tasks and ideas

### 8.2 Desktop App
- [ ] Electron or Tauri desktop wrapper
- [ ] System tray with quick capture
- [ ] Global keyboard shortcut for adding items
- [ ] Menu bar widget showing today's priorities
- [ ] Native OS notifications

---

## Phase 9: Community & Ecosystem

_Build a community around personal AI productivity._

### 9.1 Open Source Community
- [ ] Contributor documentation and guidelines
- [ ] Agent development SDK with testing framework
- [ ] Template gallery for different use cases (freelancer, student, founder, etc.)
- [ ] Self-hosted showcase — gallery of community deployments
- [ ] Discord/forum for community support

### 9.2 Templates & Presets
- [ ] Startup Founder preset — pitch tracking, investor CRM, launch checklist
- [ ] Freelancer preset — client projects, invoicing reminders, lead pipeline
- [ ] Student preset — course tracking, study schedules, research management
- [ ] Content Creator preset — content calendar, analytics tracking, idea pipeline
- [ ] Job Seeker preset — applications tracker, interview prep, networking tasks
- [ ] Researcher preset — paper reading queue, experiment tracking, citation management

### 9.3 Hosted Version (Optional)
- [ ] Managed cloud offering for non-technical users
- [ ] Free tier with basic agents and limited runs
- [ ] Onboarding flow with guided setup
- [ ] Marketplace for premium agent skills

---

## Recommended Next Sprint

_High-impact features to tackle next, prioritized by user value and feasibility._

### Sprint 5: Polish & Power User Features (Recommended)

These are the highest-leverage items that build on what we have:

1. **Inline task editing** — click to edit text, priority, tags, due dates directly in the dashboard (Phase 4.3)
2. **Filters and saved views** — filter tasks by status/priority/project, persist view preferences (Phase 4.3)
3. **Habit analytics** — streak charts, completion rates, weekly trends (Phase 3.1)
4. **Mobile-responsive design** — make the dashboard usable on phone (Phase 4.1)
5. **Dark mode toggle** — persist user theme preference (Phase 4.1)

### Sprint 6: Intelligence Boost

These make the agent system meaningfully smarter:

1. **pgvector embeddings** — semantic search instead of ILIKE (Phase 2.1)
2. **Auto-tagging** — LLM classifies new tasks and ideas automatically (Phase 2.3)
3. **Conditional triggers** — run agents when DB conditions are met, not just on schedule (Phase 2.2)
4. **Agent memory** — persistent context across runs so agents remember past decisions (Phase 2.1)
5. **Agent performance analytics** — track success rates and cost efficiency (Phase 6.3)

### Sprint 7: Integrations & Reach

These connect Mission Control to the outside world:

1. **GitHub integration** — sync issues/PRs, auto-create tasks (Phase 5.2)
2. **RSS feed ingestion** — auto-populate reading list from subscriptions (Phase 3.5)
3. **Notes table** — long-form markdown content with full CRUD (Phase 3.5)
4. **API key authentication** — secure public API access (Phase 5.4)
5. **Slack or Discord bot** — another input channel beyond Telegram (Phase 5.1)

---

## Contribution Guide

Want to help build the future of personal AI productivity?

1. **Pick a feature** from any phase above
2. **Open an issue** to discuss your approach
3. **Submit a PR** with the implementation
4. **Write a skill** — the easiest way to contribute is creating new YAML agent files

Priority areas where help is most needed:
- Agent skill files (Phase 6.2) — low barrier, high impact
- Dashboard improvements (Phase 4) — React/Next.js experience
- Integration connectors (Phase 5) — API experience with specific services
- Testing (Phase 1.3) — always needed

---

## Design Principles

These principles guide every decision:

1. **Database is truth** — All state lives in PostgreSQL. No hidden state in memory, files, or external services.
2. **Agents are config** — Agents are YAML files, not code. Anyone can create one.
3. **Human in the loop** — AI suggests, humans decide. No irreversible action without approval.
4. **Local first** — Works fully offline with Ollama. Cloud is optional, not required.
5. **Simple over clever** — A working feature beats an elegant abstraction. Ship it, then improve.
6. **Open by default** — Open source, open APIs, open formats. No lock-in.
7. **Privacy by design** — Your data stays yours. No telemetry, no analytics, no tracking.

---

*Last updated: 2026-03-17 · v0.3*
