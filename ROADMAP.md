# Mission Control Roadmap

> **Vision:** Make Mission Control the open-source personal AI command center that
> helps anyone harness AI agents for personal productivity — organizing life,
> work, learning, and side projects from a single pane of glass.

---

## Current State (v0.3)

What's already built:

- **Core data model** — Projects, tasks, ideas, reading list with full CRUD
- **Agent system** — YAML-defined skills, scheduled execution, Claude Agent SDK
- **10 agents** — Daily Standup, Reddit Scout, Idea Validator, Weekly Prioritizer, Feedback Collector, Daily Check-in, Goal Decomposer, Evening Reflection, Weekly Review, Content Drafter + template
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
- **Agent learning loop** — Run retrospective, post-run insights, action stats tracked automatically
- **Daily standup** — Conductor agent coordinates all agents via shared memory briefings
- **Shared scratchpad** — Cross-agent communication via shared memory (agent_id=NULL)
- **Output validation** — Pydantic schemas validate agent JSON before writing to DB
- **LLM retry logic** — Exponential backoff with jitter for rate limits and server errors
- **Cost & requirements doc** — Hardware specs, hosting options, per-agent API cost breakdown
- **Agent dry-run** — Preview actions without executing
- **Cross-entity search** — Search across all 7 data types + command palette (Cmd+K)
- **Webhook system** — Inbound (HMAC-verified) + outbound event dispatch + logs
- **Data export** — JSON (all entities) and CSV (per entity) downloads
- **Notification center** — In-app bell with unread count, mark read/all
- **Activity heatmap** — GitHub-style 12-week contribution graph with tooltips
- **Agent cost tracking** — Per-agent spending dashboard
- **Agent memory** — Persistent key-value context across agent runs
- **Conditional triggers** — Event-driven agent execution on DB conditions
- **Agent analytics** — Success rates, cost efficiency, daily cost sparklines
- **Auto-tagging** — LLM-based classification for tasks and ideas
- **pgvector support** — Optional embedding columns for semantic search
- **Notes system** — Long-form markdown notes with pin, tags, dashboard panel
- **API key auth** — Scoped API keys with SHA-256 hashing for public API access
- **GitHub integration** — Repo linking, webhook receiver, issue/PR sync, auto-task creation
- **RSS feeds** — Subscribe to feeds, auto-import to reading list via feedparser
- **Discord bot** — Full command set mirroring Telegram (tasks, ideas, notes, status, agents)
- **Multi-page dashboard** — Sidebar nav with 5 pages: Dashboard, Projects, Agents, Journal, Settings
- **Kanban board** — Task board view with status columns + list/board toggle
- **Bulk actions** — Multi-select tasks with bulk status, priority, delete
- **Keyboard shortcuts** — Vim-style two-key combos (g+key nav, n+key create)
- **Project dashboards** — Dedicated per-project view with all linked entities
- **Backend test suite** — 14 pytest async tests with SQLite in-memory, covering all CRUD endpoints
- **Dashboard test suite** — 21 Vitest tests for shared components and API client
- **Alembic migrations** — Async migration pipeline with initial schema (19 tables)
- **Seed data** — Example projects, tasks, habits, goals, journal, notes for new installations
- **Agent timeout** — Configurable per-agent timeout enforcement via asyncio.wait_for
- **LLM error handling** — Graceful handling of auth, rate limit, overload, network, and timeout errors
- **Routine builder** — Morning/evening routines as checklists with items, completions, and dashboard panel
- **Project health scoring** — Aggregate metrics per project with color-coded health badges on dashboard
- **Calendar view** — Monthly calendar view for tasks with due dates, priority dots, and tooltips
- **Quick capture** — Global 'c' keyboard shortcut with prefix-based type detection (t: i: r: n: h: g: j:)
- **Deduplication** — Detect near-duplicate tasks and ideas using text similarity, pre-creation check API
- **Agent workflows (DAGs)** — Multi-step agent pipelines with dependency resolution and background execution
- **Smart prioritization** — Keyword + historical pattern analysis for priority suggestions
- **Drag-and-drop task reordering** — sort_order field with HTML5 drag-and-drop in dashboard
- **Browser push notifications** — Web Push subscription management with VAPID support
- **Journal search** — Text and semantic similarity search with relevance scoring and mood filtering
- **Agent self-evaluation** — Heuristic output scoring with auto-retry on low confidence
- **Time-based context** — Agents receive time period, day of week, and behavior guidance
- **Timeline/Gantt view** — 4-week horizontal timeline with project grouping and priority bars
- **Auto-summarize reading** — LLM summarization when articles marked as read
- **Database backup/restore** — JSON backup/restore API with duplicate detection
- **User pattern learning** — Activity analysis with hourly/daily distributions and agent schedule suggestions
- **Health check diagnostics** — Per-component status with DB latency, agent stuck detection, skill files
- **Webhook templates** — 8 pre-built templates for Slack, Discord, GitHub, Stripe, Linear, Sendgrid
- **API rate limiting** — Sliding window rate limiter with per-key usage tracking
- **Agent versioning** — Automatic config snapshots on sync with version history and diffs
- **Web researcher agent** — Navigator researches topics and compiles findings into notes
- **Code review agent** — Reviewer analyzes PRs for correctness, security, and maintainability
- **Opportunity scout agent** — Scout finds freelance gigs, speaking slots, and collaborations
- **Learning path agent** — Mentor curates structured learning paths with resources
- **Health check-in agent** — Vitals provides daily wellness check-ins with pattern tracking
- **Agent marketplace** — Gallery with categories, search, one-click install, and ratings
- **Pipeline builder** — Create multi-agent workflows with dependency validation and execution preview
- **A/B testing** — Compare prompt variants with weighted traffic allocation and automatic scoring
- **Agent budget management** — Per-agent budget limits (daily/weekly/monthly) with alerts and spending history

---

## Progress Summary

| Phase | Done | Total | Progress |
|-------|------|-------|----------|
| 1. Foundation Hardening | 15 | 15 | **100%** |
| 2. Intelligence Layer | 13 | 13 | **100%** |
| 3. Personal Productivity | 15 | 23 | 65% |
| 4. Dashboard 2.0 | 18 | 18 | **100%** |
| 5. Integrations | 9 | 18 | 50% |
| 6. Multi-Agent Intelligence | 16 | 16 | **100%** |
| 7. Privacy & Scale | 0 | 16 | 0% |
| 8. Mobile & Desktop | 0 | 10 | 0% |
| 9. Community | 0 | 16 | 0% |
| **Total** | **90** | **145** | **62%** |

---

## Phase 1: Foundation Hardening

_Make what exists rock-solid and easy to set up._

### 1.1 Setup & Onboarding
- [x] One-command install script (`curl | bash` — install.sh clones repo and runs setup)
- [x] Interactive setup wizard (DB, LLM, Telegram, Discord, GitHub config with validation)
- [x] Pre-built Docker images on GitHub Container Registry (GitHub Actions workflow)
- [x] `.env` generator with validation and provider health checks
- [x] SQLite mode for zero-config local development (no Postgres required)

### 1.2 Database & Migrations
- [x] Alembic migration pipeline with async PostgreSQL support
- [x] Seed data with example projects, tasks, habits, goals, journal, notes for new users
- [x] Database backup/restore commands (`mc backup`, `mc restore`)
- [x] Data export to JSON/CSV for portability

### 1.3 Testing & Reliability
- [x] Backend test suite (pytest) — 14 async tests covering all CRUD endpoints, SQLite in-memory
- [x] Dashboard test suite (Vitest + React Testing Library) — 21 tests for components and API client
- [x] Agent dry-run mode (preview actions without executing)
- [x] Health check improvements: detailed diagnostics per component
- [x] Graceful error handling for all LLM provider failures (auth, rate limit, timeout, network)

### 1.4 Agent Robustness
- [x] Agent approval queue — human-in-the-loop before actions execute
- [x] Retry logic with exponential backoff for transient LLM failures
- [x] Agent timeout enforcement — configurable per-agent timeout with asyncio.wait_for
- [x] Output validation — Pydantic schemas reject malformed agent responses gracefully
- [x] Agent versioning — track skill file changes over time

---

## Phase 2: Intelligence Layer

_Make agents smarter and the system more context-aware._

### 2.1 Semantic Search & Memory
- [x] pgvector embeddings on tasks, ideas, and journal entries (optional, guarded import)
- [x] Semantic search API (`/api/search?q=...`) across all entities
- [x] Dashboard search bar with instant results
- [x] Agent memory — long-term context that persists across runs (key-value store per agent)
- [x] Deduplication: detect near-duplicate tasks and ideas before creating them

### 2.2 Smarter Agents
- [x] Agent chaining — output of one agent feeds into another
- [x] Conditional triggers — run agent when specific DB conditions are met
- [x] Agent-to-agent communication via shared memory scratchpad + daily standup coordination
- [x] Multi-step agent workflows (DAGs) with dependency resolution
- [x] Agent self-evaluation — score own output quality, retry if low confidence

### 2.3 Context Engine
- [x] Auto-tag tasks and ideas using LLM classification
- [x] Smart prioritization — ML-based priority suggestions from patterns
- [x] Project health scoring — aggregate metrics per project
- [x] Time-based context — "morning brief" vs "evening review" agent behavior
- [x] User pattern learning — adapt agent schedules to user activity

---

## Phase 3: Personal Productivity Suite

_Go beyond task management into a full life operating system._

### 3.1 Habits & Routines
- [x] Habits table — recurring behaviors with streak tracking
- [x] Daily check-in agent — asks about habit completion, logs streaks
- [x] Routine builder — morning/evening routines as checklists
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
- [x] Journal search with semantic similarity

### 3.4 Calendar & Time
- [ ] Calendar integration (Google Calendar, CalDAV)
- [ ] Time blocking — schedule tasks into calendar slots
- [ ] Daily agenda agent — morning briefing with today's priorities
- [ ] Meeting prep agent — gathers context before calendar events
- [ ] Deadline awareness — agents factor in due dates for prioritization

### 3.5 Knowledge Management
- [x] Notes table — long-form content with markdown support, pin/unpin, tags
- [x] Auto-summarize reading list articles when marked as read
- [ ] Spaced repetition for learning items (Anki-style)
- [ ] Web clipper (browser extension) to save articles to reading list
- [ ] YouTube/podcast transcript ingestion and summarization
- [x] RSS feed integration — auto-populate reading list from subscriptions (feedparser)

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
- [x] Multi-page layout: Dashboard, Projects, Agents, Journal, Settings (sidebar nav)
- [x] Mobile-responsive design (usable on phone)
- [x] Dark mode / light mode toggle with localStorage persistence
- [x] Keyboard shortcuts for power users (vim-style g+key nav, n+key create, Shift+T theme)
- [x] Drag-and-drop task reordering and project assignment

### 4.2 Views & Visualizations
- [x] Kanban board view for tasks (by status columns, list/board toggle)
- [x] Calendar view for tasks with due dates
- [x] Timeline/Gantt view for project planning
- [x] Agent cost dashboard — spending per agent, per day, cumulative
- [x] Activity heatmap (GitHub-style contribution graph)
- [x] Project dashboards — dedicated view per project with tasks, goals, agents, notes

### 4.3 Interactivity
- [x] Inline task editing (double-click to edit text, click priority dot to change)
- [x] Bulk actions — select multiple tasks, bulk update status/priority, bulk delete
- [x] Quick capture — global keyboard shortcut to add task/idea/reading
- [x] Filters and saved views (filter tasks by status and priority with Radix dropdowns)
- [x] Command palette (Cmd+K) for fast navigation and actions

### 4.4 Notifications & Alerts
- [x] In-app notification center for agent completions and alerts
- [x] Browser push notifications for critical events
- [ ] Daily digest email (optional)
- [ ] Customizable alert rules (e.g., "notify me when any critical task is created")

---

## Phase 5: Integrations Ecosystem

_Connect Mission Control to the tools people already use._

### 5.1 Input Channels
- [ ] Email ingestion — forward emails to create tasks/ideas
- [ ] WhatsApp bot (via WhatsApp Business API)
- [x] Discord bot — mirrors Telegram: tasks, ideas, reading, notes, status, agents
- [ ] Slack bot
- [ ] Voice input via Telegram voice messages (whisper transcription)
- [ ] iOS/Android shortcut for quick capture
- [ ] Apple Shortcuts / Siri integration

### 5.2 Service Integrations
- [x] GitHub — sync issues, PRs via webhooks; auto-create tasks from issues
- [ ] Linear — bidirectional task sync
- [ ] Notion — import/export pages and databases
- [ ] Google Workspace — Docs, Sheets, Calendar
- [ ] Stripe — revenue alerts, subscription events
- [ ] Todoist / TickTick — bidirectional task sync for existing users
- [ ] Zapier/Make webhook endpoint for connecting anything

### 5.3 Webhook System
- [x] Inbound webhooks — generic endpoint that agents can process
- [x] Outbound webhooks — notify external services on events
- [x] Webhook templates for common services
- [x] Webhook log with replay capability

### 5.4 API & Developer Platform
- [x] Public REST API with API key authentication (scoped, SHA-256 hashed)
- [x] API rate limiting and usage tracking
- [x] OpenAPI/Swagger documentation auto-generated
- [ ] SDK packages (Python, TypeScript) for programmatic access
- [ ] Plugin system — community-contributed agents and integrations

---

## Phase 6: Multi-Agent Intelligence

_Build a team of specialized AI agents that collaborate._

### 6.1 Agent Marketplace
- [x] Community agent gallery — browse and install skill files
- [x] One-click agent installation from gallery
- [x] Agent ratings and reviews
- [x] Agent categories: productivity, marketing, research, health, finance, learning

### 6.2 Advanced Agent Capabilities
- [x] Web browsing agent — research topics and summarize findings
- [x] Code review agent — review PRs and suggest improvements
- [x] Content creation agent — Echo drafts content from high-relevance marketing signals
- [x] Competitor monitoring agent — Radar tracks competitor mentions and market signals
- [x] Opportunity scout agent — find freelance gigs, speaking opportunities
- [x] Learning path agent — curate learning resources for a skill
- [x] Health check-in agent — daily wellness prompts and tracking

### 6.3 Agent Orchestration
- [x] Pipeline builder — visual editor for multi-agent workflows
- [x] Event-driven triggers (not just schedules)
- [x] Agent performance analytics — success rate, cost efficiency, action quality
- [x] A/B testing for agent prompts — compare prompt variants
- [x] Agent budget management dashboard with alerts

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

### Sprint 5: Polish & Power User Features ✅

All completed:

1. ~~**Inline task editing** — double-click to edit text, priority dropdown via Radix (Phase 4.3)~~
2. ~~**Filters and saved views** — status/priority dropdowns with Radix DropdownMenu (Phase 4.3)~~
3. ~~**Habit analytics** — weekly bar charts, completion rates, streak tracking (Phase 3.1)~~
4. ~~**Mobile-responsive design** — responsive grid layout, touch-friendly (Phase 4.1)~~
5. ~~**Dark mode toggle** — Tailwind class strategy, localStorage persistence (Phase 4.1)~~

### Sprint 6: Intelligence Boost ✅

All completed:

1. ~~**pgvector embeddings** — optional embedding columns on Task, Idea, JournalEntry (Phase 2.1)~~
2. ~~**Auto-tagging** — LLM classifies tasks/ideas via Haiku, single + batch endpoints (Phase 2.3)~~
3. ~~**Conditional triggers** — event-driven agent execution with JSON condition matching (Phase 2.2)~~
4. ~~**Agent memory** — persistent key-value store per agent, loaded in context, saveable via actions (Phase 2.1)~~
5. ~~**Agent performance analytics** — success rates, cost, duration, daily sparklines on dashboard (Phase 6.3)~~

### Sprint 7: Integrations & Reach ✅

All completed:

1. ~~**GitHub integration** — webhook receiver, issue/PR sync, auto-create tasks (Phase 5.2)~~
2. ~~**RSS feed ingestion** — subscribe to feeds, auto-import via feedparser (Phase 3.5)~~
3. ~~**Notes table** — long-form markdown with pin/unpin, tags, dashboard panel (Phase 3.5)~~
4. ~~**API key authentication** — scoped keys with SHA-256 hashing (Phase 5.4)~~
5. ~~**Discord bot** — full command set mirroring Telegram (Phase 5.1)~~

### Sprint 8: Dashboard Power-Up ✅

All completed:

1. ~~**Multi-page layout** — sidebar nav with Dashboard, Projects, Agents, Journal, Settings pages (Phase 4.1)~~
2. ~~**Kanban board** — task board view by status columns with list/board toggle (Phase 4.2)~~
3. ~~**Bulk actions** — multi-select tasks, bulk status/priority update, bulk delete (Phase 4.3)~~
4. ~~**Keyboard shortcuts** — vim-style g+key nav, n+key create, Shift+T theme, ? help (Phase 4.1)~~
5. ~~**Project dashboards** — dedicated per-project view with tasks, goals, agents, notes (Phase 4.2)~~

### Sprint 9: Foundation & Testing ✅

All completed:

1. ~~**Test suites** — pytest (14 tests, SQLite in-memory) + Vitest (21 tests, mock fetch/WS) (Phase 1.3)~~
2. ~~**Alembic migrations** — async env.py, initial migration with all 19 tables (Phase 1.2)~~
3. ~~**Seed data** — 3 projects, 7 tasks, 4 ideas, 3 reading, 4 habits, 2 goals, 1 journal, 2 notes (Phase 1.2)~~
4. ~~**Agent timeout enforcement** — configurable timeout_seconds per agent via asyncio.wait_for (Phase 1.4)~~
5. ~~**Graceful error handling** — auth, rate limit, overload, network, timeout errors with user-friendly messages (Phase 1.3)~~

### Sprint 10: Agent Intelligence & Coordination ✅

All completed:

1. ~~**Agent learning loop** — run retrospective (last 5 runs in context), post-run insights (run count, action stats, last summary auto-saved to memory) (Phase 2.2)~~
2. ~~**Shared scratchpad** — cross-agent communication via shared memory, event-driven triggers (Phase 2.2)~~
3. ~~**Daily standup agent** — Conductor coordinates all agents every morning via shared memory briefings (Phase 2.2)~~
4. ~~**Output validation** — Pydantic schemas validate agent JSON, drop malformed actions with warnings (Phase 1.4)~~
5. ~~**Retry with backoff** — exponential backoff + jitter for rate limits and server errors (Phase 1.4)~~
6. ~~**Content drafter agent** — Echo auto-drafts content from high-relevance marketing signals (Phase 6.2)~~
7. ~~**Competitor monitoring agent** — Radar tracks competitor mentions and market signals (Phase 6.2)~~
8. ~~**Cost & requirements doc** — hardware specs, hosting options, per-agent API cost breakdown~~

### Sprint 11: Productivity & Intelligence ✅

All completed:

1. ~~**Routine builder** — morning/evening routines as checklists with daily completion tracking (Phase 3.1)~~
2. ~~**Project health scoring** — aggregate metrics per project with color-coded health badges (Phase 2.3)~~
3. ~~**Calendar view** — monthly calendar showing tasks with due dates, priority dots, tooltips (Phase 4.2)~~
4. ~~**Quick capture** — global 'c' shortcut, prefix-based type detection (t: i: r: n: h: g: j:) (Phase 4.3)~~
5. ~~**Deduplication** — detect near-duplicate tasks and ideas using text similarity, pre-creation check (Phase 2.1)~~

### Sprint 12: Integrations & Automation ✅

All completed:

1. ~~**Multi-step agent workflows (DAGs)** — workflow model with steps, dependency resolution, background execution engine (Phase 2.2)~~
2. ~~**Smart prioritization** — keyword + historical pattern analysis, single and bulk suggestion APIs (Phase 2.3)~~
3. ~~**Drag-and-drop task reordering** — sort_order field, reorder API, HTML5 drag handles in dashboard (Phase 4.1)~~
4. ~~**Browser push notifications** — Web Push subscription management, VAPID support, send API (Phase 4.4)~~
5. ~~**Journal search with semantic similarity** — text + semantic search modes, relevance scoring, mood filtering (Phase 3.3)~~

### Sprint 13: Advanced Intelligence ✅

All completed:

1. ~~**Agent self-evaluation** — heuristic output scoring, auto-retry with feedback if below confidence threshold (Phase 2.2)~~
2. ~~**Time-based context** — agents receive time period, day of week, and behavior guidance in context (Phase 2.3)~~
3. ~~**Timeline/Gantt view** — 4-week horizontal timeline with project-grouped bars, priority colors, tooltips (Phase 4.2)~~
4. ~~**Auto-summarize reading** — LLM summarizes articles when marked as read, manual summarize endpoint (Phase 3.5)~~
5. ~~**Database backup/restore** — JSON backup/restore API with summary, duplicate detection on restore (Phase 1.2)~~

### Sprint 14: Scale & Ecosystem ✅

All completed:

1. ~~**User pattern learning** — activity pattern analysis, hourly/daily distributions, agent schedule suggestions based on user behavior (Phase 2.3)~~
2. ~~**Health check improvements** — detailed per-component diagnostics: DB latency, agent status, stuck detection, skill files, integrations (Phase 1.3)~~
3. ~~**Webhook templates** — 8 pre-built templates for Slack, Discord, GitHub, Stripe, Linear, Sendgrid, and generic hooks (Phase 5.3)~~
4. ~~**API rate limiting** — sliding window rate limiter (per-key/IP), usage tracking, rate limit headers on all responses (Phase 5.4)~~
5. ~~**Agent versioning** — automatic config snapshots on sync, version history, diff between versions, manual snapshots (Phase 1.4)~~

### Sprint 15: Multi-Agent Intelligence ✅

All completed — entire Phase 6 now 100%:

1. ~~**Web browsing agent** — Navigator researches topics, compiles findings into notes and reading list (Phase 6.2)~~
2. ~~**Code review agent** — Reviewer analyzes PRs for correctness, security, maintainability (Phase 6.2)~~
3. ~~**Opportunity scout agent** — Scout finds freelance gigs, speaking opportunities, collaborations (Phase 6.2)~~
4. ~~**Learning path agent** — Mentor curates structured learning paths with resources (Phase 6.2)~~
5. ~~**Health check-in agent** — Vitals provides daily wellness check-ins with pattern tracking (Phase 6.2)~~
6. ~~**Agent marketplace** — Gallery with 8 categories, search, one-click install, ratings (Phase 6.1)~~
7. ~~**Pipeline builder** — Create multi-agent workflows with dependency validation, cycle detection, execution preview (Phase 6.3)~~
8. ~~**A/B testing for prompts** — Weighted variant selection, automatic scoring, winner lock-in (Phase 6.3)~~
9. ~~**Agent budget dashboard** — Per-agent limits (daily/weekly/monthly), spending history, pre-run budget checks (Phase 6.3)~~

### Sprint 16: Streamline ✅

All completed:

1. ~~**Streamline** — removed Journal, Habits, Goals, Reading; consolidated into Notes~~

### Sprint 17: Foundation Complete ✅

All completed:

1. ~~**SQLite mode** — zero-config local dev, `USE_SQLITE=true` env var, no Postgres needed (Phase 1.1)~~
2. ~~**Interactive setup wizard** — 4-step wizard: DB, LLM, integrations, .env generation (Phase 1.1)~~
3. ~~**.env generator with validation** — API key format checks, provider health checks (Phase 1.1)~~
4. ~~**One-command install** — `curl | bash` installer clones repo and runs setup wizard (Phase 1.1)~~
5. ~~**Pre-built Docker images** — GitHub Actions workflow for GHCR publishing (Phase 1.1)~~

### Sprint 18: Productivity & Integrations (Recommended)

Next high-impact features:

1. **Calendar integration** — Google Calendar / CalDAV sync (Phase 3.4)
2. **Daily agenda agent** — morning briefing with today's priorities (Phase 3.4)
3. **Deadline awareness** — agents factor in due dates for prioritization (Phase 3.4)
4. **Spaced repetition** — Anki-style learning for reading items (Phase 3.5)
5. **Agent Builder UI** — create/edit agents from the dashboard (Phase 6.1)

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

*Last updated: 2026-03-18 · v0.4*
