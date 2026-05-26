# Freddy Agent Migration

**Date**: 2026-05-10  
**Status**: Implemented on the Strix Halo Fedora box  
**Agent**: `freddy`  
**Role**: Ben's executive assistant

## Current State

Freddy has been recreated on the Strix Halo box as a named OpenClaw agent with separate workspace, agent state, sessions, Telegram routing, and Google Calendar read access.

```text
Agent id:    freddy
Workspace:   ~/.openclaw/workspace-freddy
Agent state: ~/.openclaw/agents/freddy/agent
Sessions:    ~/.openclaw/agents/freddy/sessions
Telegram:    accountId freddy
Telegram ID: 8240038003
```

Freddy is not intended to replace `main` as the universal default agent. Telegram routing sends Ben's Freddy bot conversation to `freddy`.

## Creation Command

Freddy follows the same named-agent pattern as Tom:

```bash
openclaw agents add freddy \
  --workspace ~/.openclaw/workspace-freddy \
  --agent-dir ~/.openclaw/agents/freddy/agent \
  --bind telegram:freddy \
  --non-interactive
```

The Telegram allowlist should use Ben's Telegram user id:

```text
tg:8240038003
```

## Calendar Access

Freddy uses the shared `gog-agent` wrapper with explicit clients and accounts:

```bash
gog-agent --client ben-personal --account bbish007@gmail.com ...
gog-agent --client ben-work --account ben.b@covergenius.com ...
```

Ben's default calendar view includes three calendars:

| Calendar | Account/client | Calendar ID |
|---|---|---|
| Ben Bishop | `ben-personal` / `bbish007@gmail.com` | `primary` / `bbish007@gmail.com` |
| Ben and Helen | `ben-personal` / `bbish007@gmail.com` | `demud4un00nih20kass1tosvig@group.calendar.google.com` |
| Work | `ben-work` / `ben.b@covergenius.com` | `primary` |

List personal calendars:

```bash
gog-agent --client ben-personal --account bbish007@gmail.com calendar calendars --json --no-input
```

Default schedule queries:

```bash
gog-agent --client ben-personal --account bbish007@gmail.com calendar events primary --week --all-pages --json --no-input
gog-agent --client ben-personal --account bbish007@gmail.com calendar events 'demud4un00nih20kass1tosvig@group.calendar.google.com' --week --all-pages --json --no-input
gog-agent --client ben-work --account ben.b@covergenius.com calendar events primary --week --all-pages --json --no-input
```

For broad schedule questions, Freddy should query all three calendars, merge the results, deduplicate obvious duplicates, and present times in `America/Los_Angeles`. Include `--all-pages` on event queries; `gog-agent calendar events` defaults to 10 results and can otherwise truncate busy work days.

## Timezone Lesson

The `Ben and Helen` calendar can return events with a `+01:00` timestamp while also declaring `America/Los_Angeles` as the event timezone. Freddy's instructions now call this out explicitly and require corrected Los Angeles presentation.

## Cron Jobs

Freddy currently has these jobs:

| Name | Schedule | Purpose |
|---|---:|---|
| Daily Morning Briefing | `0 7 * * 1-5` | Query Ben Bishop, Ben and Helen, and work calendars for today's schedule, plus San Francisco weather in Fahrenheit |
| Tomorrow's Daily Briefing | `0 18 * * 0,1,2,3,4` | Query tomorrow's work, personal, and family calendars and send an evening preview |
| TLDR Tech & AI Briefing | `5 7 * * 1-5` | Fetch TLDR Tech and TLDR AI briefing |
| Health, Birthdays & Anniversaries Check | `0 8 * * 1-5` | Check all three calendars plus workspace notes for medical appointments, dentist appointments, birthdays, and anniversaries in the next 14 days |

The health/birthdays job was created manually through the CLI after Freddy repeatedly emitted malformed `cron.add` tool JSON.

The Daily Morning Briefing cron payload includes `--all-pages` on all three calendar event queries. This prevents the briefing from stopping at the first 10 work events and omitting afternoon sessions on meeting-heavy days.

The Tomorrow's Daily Briefing cron payload additionally pipes normalized calendar JSON through `calendar-daily-briefing/scripts/compact-events.py` before summarization. This prevents all-pages Google Calendar responses from flooding the model with attendees, descriptions, Meet data, attachments, links, and recurrence metadata.

The TLDR Tech & AI Briefing cron was hardened on 2026-05-18 after repeated 120-second timeouts under GPT-OSS 120B. The payload now uses a deterministic prompt that fetches only `https://tldr.tech/tech/<YYYY-MM-DD>` and `https://tldr.tech/ai/<YYYY-MM-DD>`, forbids web search/API guessing/raw HTML scraping, excludes ads/sponsors/Quick Links, and allows one previous-weekday AI fallback if today's AI issue is not published. Its `timeoutSeconds` is now `240`. A manual verification run completed successfully in about 112 seconds and delivered to Telegram.

Cron robustness changes on 2026-05-18:

- Freddy Daily Briefing, Tom Daily Briefing, Health/Birthdays, and Weekend Briefing now use `timeoutSeconds: 420` to give GPT-OSS 120B enough margin over recent p95 runtimes.
- Health/Birthdays, Tomorrow's Daily Briefing, and Weekend Briefing now have failure alerts to `telegram:8240038003` through Freddy.
- Health/Birthdays now uses `--all-pages` on all three calendar queries.
- Weekend Briefing now has a deterministic prompt: compacted calendar JSON only, `wttr.in` JSON weather, one NYT Technology page, at most three NYT headlines, one retry max, and partial output on source failure. Manual weekday validation targets the upcoming Saturday for schedule/title while scheduled weekend runs use the current day.

Manual creation pattern:

```bash
openclaw cron add \
  --agent freddy \
  --name 'Health, Birthdays & Anniversaries Check' \
  --cron '0 8 * * 1-5' \
  --tz America/Los_Angeles \
  --session isolated \
  --timeout-seconds 300 \
  --announce \
  --channel telegram \
  --account freddy \
  --to telegram:8240038003 \
  --message '<agent instructions>'
```

## Tool-Call Lesson

Qwen successfully created simpler cron jobs, but it repeatedly failed on the third cron job by producing invalid JSON keys such as:

```text
name 
payload 
schedule 
sessionTarget 
sessionTarget":
delivery": {
```

OpenClaw correctly rejected those calls with `INVALID_REQUEST`. This was a model/tool-call formatting failure, not a Telegram permission issue, cron backend issue, or session context size issue.

Practical rule: for complex cron jobs with nested payloads, use `openclaw cron add/edit` manually and let Freddy run the resulting job.

If `openclaw cron edit` fails with gateway WebSocket errors, verify with `openclaw cron list` and gateway logs before retrying. On 2026-05-18, the CLI path intermittently reported `1006 abnormal closure`; the safe fallback was to back up `~/.openclaw/cron/jobs.json`, patch only the target job, then verify via `jq`, `openclaw cron run`, and `openclaw cron runs`.

## Context and Sessions

Fresh Freddy sessions use the raised OpenClaw Qwen budget:

```text
contextTokens: 65536
```

Older sessions may still show the previous 32768 budget. Reset or start a fresh session when validating instruction changes.

## Verification

```bash
openclaw sessions --agent freddy --json --limit all
openclaw cron list
gog-agent auth list --client ben-personal
gog-agent auth list --client ben-work
gog-agent --client ben-personal --account bbish007@gmail.com calendar calendars --json --no-input
```

Do not commit Telegram tokens, OAuth client secrets, refresh tokens, or the shared `gog-agent` keyring password.
