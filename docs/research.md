# Research that could improve Mission Control

_October 2026. Eight arXiv papers that map onto real gaps in Mission Control, ordered by how much each would help. Pair this with [handoff.md](handoff.md) when planning the next round of work._

| # | Paper | What it would improve | Effort |
|---|-------|-----------------------|--------|
| 1 | [Design Patterns for Securing LLM Agents against Prompt Injections](https://arxiv.org/abs/2506.08837), with [CaMeL](https://arxiv.org/abs/2503.18813) | Safety for agents that read the web and can act | Medium |
| 2 | [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657) (MAST) | Making the coordinator reliable | Small–medium |
| 3 | [Magentic-One](https://arxiv.org/abs/2411.04468) | How the coordinator plans and recovers when stuck | Medium |
| 4 | [Agentic Context Engineering](https://arxiv.org/abs/2510.04618) (ACE) | Agents learning from your feedback | Medium |
| 5 | [Mem0](https://arxiv.org/abs/2504.19413) | Remembering facts about you across conversations | Medium |
| 6 | [Proactive Agent](https://arxiv.org/abs/2410.12361) | Suggesting work before you ask | Medium |
| 7 | [RouteLLM](https://arxiv.org/abs/2406.18665) | Lower chat usage | Small |
| 8 | [Agent Workflow Memory](https://arxiv.org/abs/2409.07429) | Reusing plans that worked | Small–medium |

**Suggested order:** #1 before relying on the scouts and one-tap publishing day to day; #4 for Echo, because draft feedback is the most direct way for the agents to learn your taste; #2 and #3 for the coordinator once it has handled a few real requests.

**Caveat:** most of these papers use benchmarks with other models, not Claude or personal-assistant work. Treat their numbers as directional, and measure on Mission Control's own run data (`agent_runs` already records cost, tokens, prompt length and transcripts for every run).

---

## 1. Prompt-injection design patterns, and CaMeL

[arXiv:2506.08837](https://arxiv.org/abs/2506.08837) (2025) · [arXiv:2503.18813](https://arxiv.org/abs/2503.18813) (Google, Google DeepMind, ETH Zurich, 2025; [code](https://github.com/google-research/camel-prompt-injection))

**What they say.** Models can't be relied on to resist instructions hidden in the text they read, so the system has to limit what an agent can do once it has read untrusted text. The design-patterns paper describes ways to do that, such as "plan, then execute" (decide the actions before reading untrusted content) and keeping untrusted content away from the part that chooses actions. CaMeL implements the second idea with two models: a privileged one that plans from the user's request, and a quarantined one that processes untrusted data and has no tools.

**Why it matters here.** Pulse and Navigator read Reddit posts and web pages that anyone can write. The same agents can create tasks, hand work to teammates (Pulse → Echo), and lead to drafts that can be published to X or LinkedIn. A hostile post could try to steer any of that.

**What to build**
- Agents with `web_search` get their `handoff`, `follow_up` and write actions routed through approval automatically, or are limited to a narrow set of actions.
- Text that came from the web is passed between agents as clearly labelled, quoted data (for example in a fenced block marked "untrusted content"), never mixed into the instructions of a handoff request.
- Keep the human confirm step on publishing (already there); it's exactly the kind of checkpoint the paper recommends.

## 2. Why do multi-agent LLM systems fail? (MAST)

[arXiv:2503.13657](https://arxiv.org/abs/2503.13657) (UC Berkeley, 2025; dataset and grader released)

**What it says.** The authors annotated about 1,600 runs from 7 multi-agent frameworks and grouped failures into 14 types in three categories: system design issues, misalignment between agents, and missing verification. Agents ignore each other's output, repeat steps, stop too early, or never check the result. Most failures come from design, not from model limits. Multi-agent setups often barely beat a single agent or best-of-N sampling.

**Why it matters here.** It is a checklist for the coordinator (Ace), which is new and hasn't run on real requests yet.

**What to build**
- A verification step in the coordinator's final round: before answering, check the combined answer against the user's original request.
- Run the paper's failure taxonomy and LLM grader over our stored run transcripts to see how Ace actually fails.
- Compare coordinated requests with Ace working alone on the same requests, on quality and cost, to confirm the coordinator earns its extra runs.

## 3. Magentic-One

[arXiv:2411.04468](https://arxiv.org/abs/2411.04468) (Microsoft Research, 2024; available in AutoGen as `MagenticOneGroupChat`)

**What it says.** A lead orchestrator keeps two records:
- a **task ledger**: the facts it has, its educated guesses, and the plan;
- a **progress ledger**: each round, an explicit check of whether the task is done, whether it's progressing, and who should act next, with a count of stalled rounds that triggers re-planning.

**Why it matters here.** Ace currently sees the thread and a list of what it handed out (`coordinator.team_status`). It has no structured memory of the plan between rounds and no notion of being stuck. The AutoGen docs also warn that web pages can inject instructions, which supports #1.

**What to build**
- Store a small JSON ledger on the request task (facts, plan, progress, stall count); Ace updates it each round with a new action.
- Put the ledger in Ace's prompt in place of most of the raw thread, which also makes later rounds cheaper.
- Re-plan, or ask the user, after two stalled rounds, instead of only relying on the 5-round cap.

## 4. Agentic Context Engineering (ACE)

[arXiv:2510.04618](https://arxiv.org/abs/2510.04618) (Stanford, SambaNova, UC Berkeley; ICLR 2026)

**What it says.** Each agent keeps an evolving "playbook" of bullet points. After each run, a reflection step adds or edits individual bullets (with counters for how often each helped or hurt) instead of rewriting the whole thing, which avoids losing detail through repeated summarizing ("context collapse"). It learns from outcomes without labelled examples. It reports +10.6% on agent benchmarks.

**Why it matters here.** Agent memory today is plain key/value pairs (`agent_memories`) that an agent writes when it remembers to. Echo's drafts produce a steady feedback signal that nothing learns from: you approve, edit, discard or publish each one.

**What to build**
- A per-agent playbook, injected into its prompt.
- After a draft is approved, edited, discarded or published, a cheap reflection run (Haiku) compares the draft with what happened (including the diff of your edits) and adds or updates bullets: "cuts the opening sentence", "no hashtags on LinkedIn".
- The same loop for task replies: a reply followed by "thanks" versus a correction.

## 5. Mem0

[arXiv:2504.19413](https://arxiv.org/abs/2504.19413) (2025; by the company behind Mem0)

**What it says.** After each exchange, extract salient facts, then for each one decide whether to add it, update an existing fact, delete a contradicted one, or do nothing. Retrieve only the relevant facts for later prompts. It reports over 90% lower token cost than sending the full history (vendor-reported).

**Why it matters here.** The Telegram chat remembers the last 20 messages for 30 minutes, and `workspace/identity.md` never changes. Facts like "launching on the 20th" or "prefers a casual tone" are lost.

**What to build**
- A `user_facts` table maintained by a cheap extraction step after chat messages and task replies (add, update, delete or ignore).
- The relevant facts go into the chat's and the agents' prompts, next to `identity.md`.
- A Settings page section to see and delete what it remembers.

## 6. Proactive Agent

[arXiv:2410.12361](https://arxiv.org/abs/2410.12361) (Tsinghua, 2024; [code](https://github.com/thunlp/ProactiveAgent))

**What it says.** An assistant that proposes tasks before being asked, trained and evaluated on real activity traces. Its key finding is that suggestions must be filtered by a model of whether people accept them, or they quickly become noise.

**Why it matters here.** Mission Control mostly waits to be asked. The morning briefing and Atlas's weekly review are natural places to propose work.

**What to build**
- The briefing (or Atlas) proposes two or three tasks, each with **Accept** / **Dismiss** buttons (the button machinery already exists).
- Record each decision, and use accepted and dismissed suggestions as examples in the prompt that generates the next ones, so dismissals act as the filter.

## 7. RouteLLM

[arXiv:2406.18665](https://arxiv.org/abs/2406.18665) (UC Berkeley, Anyscale, Canva; ICLR 2025; [code](https://github.com/lm-sys/RouteLLM))

**What it says.** A small router trained on preference data decides, per request, whether a strong or a cheap model is needed. It more than halved cost without losing quality.

**Why it matters here.** Every Telegram chat message goes to Sonnet (`CHAT_MODEL`), including "add a task: buy milk", and chat is the busiest path.

**What to build**
- Start rule-based: short capture-style messages (tasks, notes, reminders, status questions) go to Haiku; anything mentioning agents, research or writing goes to Sonnet.
- Log the routing decisions; only consider a learned router if the rules misroute often.

## 8. Agent Workflow Memory

[arXiv:2409.07429](https://arxiv.org/abs/2409.07429) (CMU, MIT; ICML 2025)

**What it says.** Successful runs are turned into reusable routines ("workflows") and given back to the agent on similar tasks. It improves success by 24.6% on Mind2Web and 51.1% on WebArena (relative), with fewer steps.

**Why it matters here.** Ace will see the same kinds of requests again (comparisons, launch posts, weekly content).

**What to build**
- When a coordinated request finishes and you don't correct it, save its plan (which teammates, in what order, with what instructions) as a routine.
- Show the closest saved routines in Ace's prompt for new requests.
- This overlaps with #4; build one or the other.

---

## Sources

- Design Patterns for Securing LLM Agents against Prompt Injections — https://arxiv.org/abs/2506.08837
- Defeating Prompt Injections by Design (CaMeL) — https://arxiv.org/abs/2503.18813
- Why Do Multi-Agent LLM Systems Fail? — https://arxiv.org/abs/2503.13657
- Magentic-One: A Generalist Multi-Agent System for Solving Complex Tasks — https://arxiv.org/abs/2411.04468 · AutoGen docs: https://microsoft.github.io/autogen/
- Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models — https://arxiv.org/abs/2510.04618
- Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory — https://arxiv.org/abs/2504.19413
- Proactive Agent: Shifting LLM Agents from Reactive Responses to Active Assistance — https://arxiv.org/abs/2410.12361
- RouteLLM: Learning to Route LLMs with Preference Data — https://arxiv.org/abs/2406.18665
- Agent Workflow Memory — https://arxiv.org/abs/2409.07429
