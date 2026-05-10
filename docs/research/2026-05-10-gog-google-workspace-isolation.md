# gog Google Workspace Isolation

**Date**: 2026-05-10  
**Status**: Research / implementation plan  
**Goal**: Give Tom controlled access to Helen's Google Workspace, starting with Calendar, without leaking those credentials to other OpenClaw agents.

## Current state

OpenClaw includes a bundled `gog` skill for Google Workspace:

- Gmail
- Calendar
- Drive
- Contacts
- Sheets
- Docs

On the Strix Halo box, the skill is present but needs setup, and `gog` is not currently installed.

## Isolation problem

OpenClaw agent isolation covers agent workspaces, state directories, sessions, and identities. It does not automatically isolate third-party CLI credential stores.

`gog` is an external CLI. If it uses the default config directory for the `ben` Unix user, then all OpenClaw agents running as `ben` may be able to use the same Google OAuth credentials when they can execute `gog`.

That is not acceptable for Helen's account. Tom should own Helen's Google Workspace access; Bernie, Freddy, and Archie should not inherit it.

This is configuration isolation, not a hard security boundary by itself. If all agents can run arbitrary shell commands as the same Unix user, they can potentially read files owned by that user. Stronger isolation requires sandbox policy, separate OS users, containers, or narrower tool permissions.

## Recommended design

Use a Tom-specific config root and a wrapper command.

```text
~/.openclaw/agents/tom/gog-config/
```

Recommended permissions:

```bash
chmod 700 ~/.openclaw/agents/tom/gog-config
```

Run `gog` for Tom with:

```bash
XDG_CONFIG_HOME="$HOME/.openclaw/agents/tom/gog-config" \
GOG_ACCOUNT="<helen-google-account>" \
gog ...
```

Do not configure this `XDG_CONFIG_HOME` for other agents.

## Wrapper command

Create a small wrapper such as `tom-gog` on the Strix Halo box:

```bash
#!/usr/bin/env bash
set -euo pipefail

export XDG_CONFIG_HOME="$HOME/.openclaw/agents/tom/gog-config"
export GOG_ACCOUNT="<helen-google-account>"

exec gog "$@"
```

Tom's instructions should use `tom-gog`, not raw `gog`, for Helen's Google Workspace.

## Initial scope

Start with Google Calendar only.

Setup flow:

```bash
tom-gog auth credentials /path/to/client_secret.json
tom-gog auth add <helen-google-account> --services calendar
tom-gog auth list
```

Calendar read test:

```bash
tom-gog calendar events primary \
  --from 2026-05-10T00:00:00-07:00 \
  --to 2026-05-17T00:00:00-07:00 \
  --json \
  --no-input
```

Use read-only OAuth scopes if `gog` supports them cleanly. If `gog` grants broader Calendar access, enforce write restrictions through Tom's instructions and wrapper policy.

## Approval policy

Tom may:

- Read Helen's calendar to answer scheduling questions.
- Summarize upcoming events.
- Find possible openings.
- Draft proposed events or schedule changes.

Tom must ask before:

- Creating calendar events.
- Updating or deleting events.
- Inviting guests.
- Sending calendar notifications.
- Sending email or creating Gmail drafts.
- Accessing Drive, Docs, Sheets, Contacts, or Gmail beyond the enabled service scope.

## Future expansion

Recommended order after Calendar works:

1. Contacts read access for better scheduling context.
2. Gmail read access for travel and scheduling context.
3. Gmail draft creation, still approval-gated.
4. Drive and Docs read access.
5. Calendar writes, only after approval behavior is reliable.

Each expansion should use the same Tom-specific `XDG_CONFIG_HOME` and should be documented in Tom's workspace.

## Verification

After setup:

```bash
command -v gog
tom-gog auth list
tom-gog calendar events primary --from <iso> --to <iso> --json --no-input
openclaw skills list
```

Expected:

- `gog` is installed.
- Tom's isolated config contains Helen's OAuth credentials.
- Other agents are not configured to use Tom's `gog-config`.
- Tom's workspace documents that Google actions are approval-gated.

## Secret hygiene

Do not commit:

- Google OAuth client secrets.
- `gog` token files.
- Refresh tokens.
- Helen's actual account address if this repository may be shared.

Use placeholders in docs and keep real credentials under the Tom-specific config root on the Strix Halo box.
