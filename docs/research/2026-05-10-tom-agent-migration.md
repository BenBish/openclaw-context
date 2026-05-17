# Tom Agent Migration

**Date**: 2026-05-10  
**Status**: Implemented on the Strix Halo Fedora box  
**Agent**: `tom`  
**Role**: Helen's executive assistant

## Current State

Tom is installed as a named OpenClaw agent with a separate workspace, agent state directory, Telegram binding, and Google Calendar read access through the shared `gog-agent` wrapper.

```text
Agent id:    tom
Workspace:   ~/.openclaw/workspace-tom
Agent state: ~/.openclaw/agents/tom/agent
Sessions:    ~/.openclaw/agents/tom/sessions
Telegram:    accountId tom
```

Tom is not the global default agent. Telegram routing sends Helen's Telegram conversation to `tom`; TUI sessions should use full session keys when targeting Tom explicitly.

## Creation Command

Tom was created with OpenClaw's scaffold command:

```bash
openclaw agents add tom \
  --workspace ~/.openclaw/workspace-tom \
  --agent-dir ~/.openclaw/agents/tom/agent \
  --bind telegram:tom \
  --non-interactive
```

The generated config was then edited for Telegram token/allowlist, model defaults, and workspace instructions.

## Calendar Access

Tom uses the shared `gog-agent` wrapper. Calendar access is policy-separated by explicit client/account flags:

```bash
gog-agent --client helen --account helen.bicknell@hotmail.co.uk calendar calendars --json --no-input
```

Helen's default calendar view includes:

| Calendar | ID | Notes |
|---|---|---|
| Helen primary | `helen.bicknell@hotmail.co.uk` | Primary calendar |
| Ben and Helen | `demud4un00nih20kass1tosvig@group.calendar.google.com` | Joint scheduling calendar |
| NVNS | `noevalleycoop@gmail.com` | School calendar |

Useful event query:

```bash
gog-agent --client helen --account helen.bicknell@hotmail.co.uk calendar events \
  --from <iso-start> \
  --to <iso-end> \
  --all \
  --json \
  --no-input
```

## Timezone Lesson

Helen is in `America/Los_Angeles`. The `Ben and Helen` calendar can return events whose `dateTime` uses a `+01:00` offset while the event timezone says `America/Los_Angeles`. Tom now has the same workspace-local `gog-calendar-timezones` skill as Freddy and is instructed to use its `calendar-query.sh` wrapper for calendar event reads before summarizing.

For daily briefings, a wider query window is safer than a narrow `--today` query because timezone-bugged events can appear on adjacent UTC/local dates. Tom should normalize with the skill wrapper first, then filter/present the correct local day.

## Daily Briefing Cron

Tom has a daily Telegram briefing:

```text
Name:       Daily Briefing
Schedule:   0 7 * * *
Timezone:   America/Los_Angeles
Delivery:   telegram:7971152269 via account tom
```

The briefing includes Helen's calendars and San Francisco weather. It is delivered to Helen through Tom's Telegram account.

## Operational Notes

- `openclaw tui --session tom` is not the same as selecting agent `tom`; it only selects the session name.
- Use full keys for TUI targeting, for example `openclaw tui --session agent:tom:tom`.
- Telegram routing is the source of truth for Helen's Telegram conversation.
- Tom should ask before calendar writes, invites, notifications, email actions, or access to services outside the configured Calendar scope.
- If a Telegram session behaves as though it has old instructions, start a new session or reset the chat session so Tom reloads current workspace instructions.

## Verification

```bash
openclaw agents list --bindings
openclaw sessions --agent tom
gog-agent auth list --client helen
gog-agent --client helen --account helen.bicknell@hotmail.co.uk calendar calendars --json --no-input
```

Do not commit Telegram tokens, OAuth client secrets, refresh tokens, or the shared `gog-agent` keyring password.
