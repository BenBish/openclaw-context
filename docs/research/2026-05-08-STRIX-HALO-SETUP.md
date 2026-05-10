# OpenClaw Multi-Agent Setup - Strix Halo Box

**Target**: Fedora Strix Halo box, 128GB RAM, AMD GPU  
**Runtime**: OpenClaw 2026.5.7, gateway managed by user systemd  
**Model backend**: local llama.cpp / llama-swap at `http://localhost:8080/v1`  
**Current state**: Tom is implemented; Bernie, Freddy, and Archie are future migrations.

## Current Agents

| Name | Status | Role | Workspace | Agent state |
|---|---|---|---|---|
| `main` | Active scaffold/default | Neutral OpenClaw default agent | `~/.openclaw/workspace` | `~/.openclaw/agents/main/agent` |
| `tom` | Implemented | Helen's executive assistant | `~/.openclaw/workspace-tom` | `~/.openclaw/agents/tom/agent` |
| `bernie` | Future | Polymarket / sports betting research | TBD | TBD |
| `freddy` | Future | Expert Advisor / trading | TBD | TBD |
| `archie` | Future | Coding expert | TBD | TBD |

`main` intentionally remains the default scaffold agent. Tom is reached by explicit Telegram routing or by using a full TUI session key.

## What Was Done

Tom was created with OpenClaw's scaffolding commands instead of writing the config from scratch:

```bash
openclaw setup
openclaw agents add tom \
  --workspace ~/.openclaw/workspace-tom \
  --agent-dir ~/.openclaw/agents/tom/agent \
  --bind telegram:tom \
  --non-interactive
```

Then the generated config was edited only for local models, Telegram account settings, Tom's workspace identity files, and context/compaction tuning.

## Routing and Sessions

Telegram account `tom` routes to agent `tom`:

```json5
{
  type: "route",
  agentId: "tom",
  match: {
    channel: "telegram",
    accountId: "tom",
  },
}
```

For TUI use, `--session` is a session key, not an agent flag. Use full keys when targeting a named agent:

```bash
openclaw tui --session agent:tom:tom
openclaw tui --session agent:tom:main
```

Plain `openclaw tui` opens the default `main` agent unless the default agent is changed.

## Model Configuration

The active model provider is `local-llama`, backed by the local OpenAI-compatible llama.cpp endpoint:

```json5
models: {
  mode: "merge",
  providers: {
    "local-llama": {
      baseUrl: "http://localhost:8080/v1",
      auth: "api-key",
      api: "openai-completions",
      timeoutSeconds: 300,
      request: {
        allowPrivateNetwork: true,
      },
      models: [
        {
          id: "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
          contextWindow: 131072,
          contextTokens: 32768,
          maxTokens: 4096,
        },
        {
          id: "gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf",
          contextWindow: 32768,
          contextTokens: 32768,
          maxTokens: 4096,
        },
      ],
    },
  },
}
```

Agent defaults point at Qwen with Gemma as fallback:

```json5
agents: {
  defaults: {
    model: {
      primary: "local-llama/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
      fallbacks: ["local-llama/gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf"],
      timeoutMs: 300000,
    },
  },
}
```

Current model check:

```bash
openclaw models list
```

Expected context display:

```text
Qwen:  32k/128k default
Gemma: 32k      fallback#1
```

## Context and Compaction

The effective context budget is 32k even though Qwen's native window is 128k. This keeps Tom responsive while the deployment is being validated.

```json5
agents: {
  defaults: {
    compaction: {
      reserveTokens: 8192,
      keepRecentTokens: 12000,
      reserveTokensFloor: 0,
      notifyUser: true,
    },
  },
}
```

`tokens ?/33k` in the TUI is acceptable. The `?` means OpenClaw does not yet have a fresh token count for that session; the `33k` reflects the configured effective context.

## Tom Workspace

Tom's workspace files live in `~/.openclaw/workspace-tom`:

- `IDENTITY.md` - Tom, Helen's executive assistant
- `SOUL.md` - warm, discreet, efficient, proactive
- `USER.md` - Helen-specific context, initially sparse
- `AGENTS.md` - scheduling, planning, correspondence drafting, research, reminders, and approval rules

Tom should not claim access to calendar, email, accounts, or devices unless the relevant tool context proves it is configured.

## Verification

Use these commands after config changes:

```bash
openclaw config validate
openclaw agents list --bindings
openclaw models list
openclaw channels status
curl http://localhost:8080/v1/models
```

Useful session checks:

```bash
openclaw sessions --agent tom
openclaw sessions --agent main
```

Telegram messages to Tom's bot should create or update sessions under:

```text
~/.openclaw/agents/tom/sessions/
```

## Future Agent Additions

Add Bernie, Freddy, and Archie with the same pattern:

```bash
openclaw agents add <agent-id> \
  --workspace ~/.openclaw/workspace-<agent-id> \
  --agent-dir ~/.openclaw/agents/<agent-id>/agent \
  --bind telegram:<agent-id> \
  --non-interactive
```

Each named agent should get:

- A separate workspace
- A separate `agentDir`
- A dedicated Telegram account/bot unless there is a deliberate routing reason
- Explicit bindings
- No inherited third-party CLI credentials unless intentionally configured

Only enable broad subagent or agent-to-agent access after all agents are installed and tested.

## Secret Hygiene

Do not commit:

- Telegram bot tokens
- Gateway auth tokens
- Google OAuth client secrets
- Google refresh tokens
- Per-agent external CLI credential stores

The repo should contain placeholders and operational notes only.
