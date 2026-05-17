# Multi-Agent Architecture Analysis

**Date**: 2026-05-09
**Source**: OpenClaw docs (docs.openclaw.ai)

---

## Agents are fully isolated by design

Each agent gets its own:
- **Workspace** (SOUL.md, AGENTS.md, USER.md, skills)
- **State directory** (auth profiles, model registry, per-agent config)
- **Session store** (independent chat history under `~/.openclaw/agents/<agentId>/sessions`)
- **Personality** — no shared memories, no shared context, no shared identity

They do **not** share anything out of the box. No cross-talk, no shared memory, no shared personality.

---

## Built-in inter-agent communication mechanisms

This is the key advantage over a Slack group. OpenClaw has explicit, structured inter-agent communication:

### 1. Sub-agents (`sessions_spawn`) — primary mechanism

- Any agent can spawn a sub-agent under *another agent's* identity
- Example: Tom spawns a sub-agent as Bernie to do Polymarket research
- Results announce back automatically to the caller chat channel
- Configurable via `agents.defaults.subagents.allowAgents` (set `["*"]` to allow cross-agent spawning)
- Supports nested depth (orchestrator pattern: main → orchestrator sub-agent → worker sub-sub-agents)
- Context modes: `isolated` (fresh transcript) or `fork` (branches current conversation)
- Max nesting depth: 5 (2 recommended for most use cases)
- Max concurrent sub-agents: 8 per agent (default)
- Auto-archive after 60 minutes (configurable)

### 2. Agent-to-agent messaging (`tools.agentToAgent`)

- Explicit allowlist of agents that can message each other
- Disabled by default, must be explicitly enabled in config
- More like direct messaging between agents
- Config example:
  ```json5
  tools: {
    agentToAgent: {
      enabled: true,
      allow: ["bernie", "freddy", "archie", "tom"],
    },
  }
  ```

### 3. QMD memory search

- One agent can search another agent's session transcripts
- Via `agents.list[].memorySearch.qmd.extraCollections`
- Returns a bounded, sanitized view — not a raw transcript dump
- Assistant recall strips thinking tags, tool-call XML, control tokens, and credentials

### 4. Sessions tools (`sessions_history`, `sessions_send`, `sessions_list`)

- Agents can read other sessions' history and send messages to them
- These are gated by tool policy (denied by default for sub-agents)
- `sessions_history` is the safer orchestration path — sanitized and bounded

---

## Downsides of one-install multi-agent

1. **Single point of failure** — one Gateway crash takes down all agents
2. **Resource contention** — all agents share the same process memory and model inference. With local llama.cpp, concurrent sub-agent calls queue up
3. **Config complexity** — one wrong binding routes messages to the wrong agent
4. **Auth collisions** — accidentally sharing `agentDir` between agents causes auth/session collisions (OpenClaw explicitly warns against this)
5. **Update risk** — upgrading OpenClaw affects all agents simultaneously
6. **External CLI credentials are not automatically isolated** — tools such as `gog`, `gh`, or other command-line clients may use the Unix user's default config directory unless explicitly redirected per agent.

## Upsides

- **True inter-agent communication** — far more structured than Slack, with announce-back, task tracking, and nested orchestration
- **Single update surface** — one `npm update` or `brew upgrade`
- **Shared model inference** — llama.cpp loads the model once in VRAM, all agents share it (critical on a single GPU)
- **Unified session management** — one Gateway process handles routing, channels, sessions

## External tool isolation

OpenClaw isolates workspaces, agent state, and session stores, but that does not automatically isolate external CLI tools launched under the same Unix user. A CLI that reads `~/.config`, `~/.local/share`, browser profiles, keychains, or default credential files can become shared across agents unless its environment is scoped.

For sensitive integrations, use per-agent config roots and wrapper commands. Example policy:

- Tom uses the workspace-local `gog-calendar-timezones` wrapper with explicit `--client helen --account ...` flags for Helen's calendar event reads.
- Freddy uses explicit `gog-agent --client ben-personal` and `--client ben-work` commands for Ben's calendars.
- Freddy's default calendar view is not just one personal calendar: it includes Ben Bishop, Ben and Helen, and work.
- Bernie and Archie should not get calendar instructions unless intentionally configured later.
- This shared `gog-agent` setup is policy separation, not a hard security boundary; stronger isolation would require per-agent config roots, separate OS users, containers, or narrower tool permissions.

## Runtime lessons from Tom and Freddy

- Keep `main` as a neutral scaffold/default agent; route named Telegram bots to named agents with account-specific routes.
- `openclaw tui --session <name>` selects a session name, not an agent. Use a full key such as `agent:tom:tom` or rely on Telegram routing.
- New Qwen sessions should show an effective OpenClaw context around 64k. Older sessions can retain their previous 32k budget.
- Session reset/new-session is the clean way to make Telegram conversations reload updated workspace instructions.
- External calendar timezones need deterministic normalization. The shared `Ben and Helen` calendar can return `+01:00` timestamps while declaring `America/Los_Angeles`; both Tom and Freddy now use the workspace-local `gog-calendar-timezones` wrapper for event reads before presentation.
- Calendar event pagination matters for busy days. `gog-agent calendar events` defaults to 10 results, so briefing and schedule-summary queries should include `--all-pages`.
- All-pages calendar responses can be too verbose for cron agents. Cron-delivered daily briefings should compact normalized event JSON before the model sees it.
- For complex cron payload creation, prefer `openclaw cron add/edit` from the CLI. Qwen repeatedly produced malformed nested cron tool JSON even in a fresh 64k session.

---

## Key config for enabling inter-agent communication

```json5
{
  agents: {
    defaults: {
      subagents: {
        maxConcurrent: 8,
        maxSpawnDepth: 2,
        allowAgents: ["*"],  // allow any agent to spawn any other
      },
    },
    list: [
      { id: "bernie", workspace: "~/.openclaw/workspace-bernie" },
      { id: "freddy", workspace: "~/.openclaw/workspace-freddy" },
      { id: "archie", workspace: "~/.openclaw/workspace-archie" },
      { id: "tom", workspace: "~/.openclaw/workspace-tom" },
    ],
  },
  tools: {
    agentToAgent: {
      enabled: true,
      allow: ["bernie", "freddy", "archie", "tom"],
    },
  },
}
```
