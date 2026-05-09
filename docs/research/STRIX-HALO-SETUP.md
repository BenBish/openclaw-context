# Openclaw Multi-Agent Setup — Strix Halo Box

**Target**: Fedora Strix Halo box (128GB RAM, AMD GPU)
**Laptop**: Omarchy (dev machine)
**Llama.cpp**: Running via ROCm Toolboxes, serving both models locally
**Channel**: Telegram (new bot to be created)

---

## Agents

| # | Name | Role | Source |
|---|------|------|--------|
| 1 | **Bernie** | Polymarket / sports betting research specialist | `~/.openclaw/` on this laptop |
| 2 | **Freddy** | Expert Advisor (trading) | `~/.openclaw/` on another laptop |
| 3 | **Archie** | Coding expert | `~/.openclaw-archie/` on another laptop |
| 4 | **Helen** | Personal assistant (new) | Fresh workspace on Strix Halo |

All agents run on local Llama.cpp models — no cloud API keys needed.

---

## Step 1 — Create Telegram Bot

1. Open Telegram, message `@BotFather`
2. `/newbot` → name it, set a username (e.g., `openclaw_assistant_bot`)
3. Copy the **Bot Token** (format: `000000000:AAAXXXXXXXXXXXXXXXXXXXXXXXXXX`)
4. Store the token in `~/.openclaw/auth/telegram.json` or equivalent — **do not commit to git**

---

## Step 2 — Set Up Llama.cpp Server (Persistent)

The Strix Halo box already has Llama.cpp/ROCm running. Configure it as a persistent systemd service:

```ini
# /etc/systemd/system/openclaw-llama.service
[Unit]
Description=Openclaw Llama.cpp Server
After=network.target

[Service]
Type=simple
User=ben
ExecStart=/path/to/llama-server \
  --model /path/to/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  --ctx-size 8192 \
  --n-gpu-layers 99 \
  --embedding \
  --chat-template qwen2.5
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable --now openclaw-llama.service
```

Verify:
```bash
curl http://localhost:8080/v1/models
```

**Model choice**: Qwen3.6-35B-3B-UD-Q4_K_XL.gguf as the default for all agents.
Gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf available as an alternate if needed (lower VRAM usage).

---

## Step 3 — Migrate Agent State

### 3a. Bernie (from laptop `~/.openclaw/`)
```bash
# On laptop (source):
rsync -avz ~/.openclaw/agents/bernie/ ben@<strix-halo-ip>:~/.openclaw/agents/bernie/
rsync -avz ~/.openclaw/workspace/ ben@<strix-halo-ip>:~/.openclaw/workspace/
```

### 3b. Freddy (from another laptop `~/.openclaw/`)
```bash
# On source laptop:
rsync -avz ~/.openclaw/agents/freddy/ ben@<strix-halo-ip>:~/.openclaw/agents/freddy/
```

### 3c. Archie (from another laptop `~/.openclaw-archie/`)
```bash
# On source laptop:
rsync -avz ~/.openclaw-archie/agents/archie/ ben@<strix-halo-ip>:~/.openclaw/agents/archie/
```

### 3d. Helen (new, on Strix Halo)
Create fresh workspace:
```bash
mkdir -p ~/.openclaw/agents/helen/workspace
```

---

## Step 4 — Openclaw Configuration

### `~/.openclaw/openclaw.json`

```json5
{
  "agents": {
    "list": [
      {
        "id": "bernie",
        "name": "Bernie",
        "agentDir": "~/.openclaw/agents/bernie"
      },
      {
        "id": "freddy",
        "name": "Freddy",
        "agentDir": "~/.openclaw/agents/freddy"
      },
      {
        "id": "archie",
        "name": "Archie",
        "agentDir": "~/.openclaw/agents/archie"
      },
      {
        "id": "helen",
        "name": "Helen",
        "agentDir": "~/.openclaw/agents/helen"
      }
    ],
    "defaults": {
      "model": {
        "provider": "openai",
        "apiBase": "http://localhost:8080/v1",
        "model": "Qwen3.6-35B-A3B-UD-Q4_K_XL"
      },
      "env": {
        "OPENAI_API_KEY": "fake-key-for-local"
      }
    }
  },
  "bindings": [
    {
      "channel": "telegram",
      "accountId": "openclaw-telegram",
      "agentId": null,
      "allowFrom": ["<your-telegram-user-id>"]
    }
  ],
  "auth": {
    "profiles": {
      "telegram": {
        "token": "000000000:AAAXXXXXXXXXXXXXXXXXXXXXXXXXX"
      }
    }
  },
  "sandboxing": {
    "enabled": false
  },
  "skipBootstrap": false
}
```

### Per-Agent Workspace Files

Each agent directory `~/.openclaw/agents/<id>/workspace/` should contain:

- `AGENTS.md` — Agent instructions, capabilities, and behavioral guidelines
- `SOUL.md` — Personality, tone, and identity
- `USER.md` — Information about the user (you)
- `IDENTITY.md` — Agent's own identity and name

**Helen's workspace** should be initialized with her identity as a personal assistant:
- `SOUL.md` — Warm, helpful, proactive personal assistant
- `USER.md` — Your preferences, habits, schedule, pet names, etc.
- `AGENTS.md` — What Helen can do (reminders, research, planning, etc.)
- `IDENTITY.md` — "I am Helen, [your name]'s personal assistant..."

---

## Step 5 — Bootstrap & Verify

1. **Start Openclaw** on the Strix Halo box:
   ```bash
   openclaw start
   ```

2. **Verify each agent** can respond:
   - Send a test message to the Telegram bot
   - Confirm the correct agent responds (routing via bindings)

3. **Check memory/state** — ensure migrated agents retain their prior context

4. **Monitor GPU usage** — watch ROCm/meminfo to ensure models load correctly:
   ```bash
   rocm-smi
   ```

---

## File Structure on Strix Halo

```
~/.openclaw/
├── openclaw.json                    # Global config
├── auth/
│   └── telegram.json                # Telegram bot token (git-ignored)
├── agents/
│   ├── bernie/
│   │   ├── workspace/
│   │   │   ├── AGENTS.md
│   │   │   ├── SOUL.md
│   │   │   ├── USER.md
│   │   │   └── IDENTITY.md
│   │   └── state/                   # Prior context, memory, etc.
│   ├── freddy/
│   │   ├── workspace/
│   │   └── state/
│   ├── archie/
│   │   ├── workspace/
│   │   └── state/
│   └── helen/
│       └── workspace/
│           ├── AGENTS.md
│           ├── SOUL.md
│           ├── USER.md
│           └── IDENTITY.md
└── workspace/                       # Default/shared workspace
```

---

## Notes

- **Git hygiene**: `auth/telegram.json` and any files containing API keys should be in `.gitignore`
- **Model swap**: If Qwen3.6-35B is too heavy, switch the llama-server `--model` to the Gemma-4-26B variant
- **Per-agent model override**: Each agent can override the default model in its own config within `agentDir`
- **Bootstrap**: First-run creates the 4 bootstrap files. They're removed after completion. If you want to customize them, either edit them after creation or set `skipBootstrap: false` and let them generate, then overwrite
