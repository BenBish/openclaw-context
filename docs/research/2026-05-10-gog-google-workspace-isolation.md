# gog Google Workspace Isolation

**Date**: 2026-05-10
**Status**: Research / implementation notes
**Goal**: Give trusted family agents access to clearly named Google Workspace accounts, starting with Tom reading Helen's Calendar and Freddy reading Ben's calendars.

## Current state

OpenClaw includes a bundled `gog` skill for Google Workspace:

- Gmail
- Calendar
- Drive
- Contacts
- Sheets
- Docs

On the Strix Halo box, `gog` is installed at `~/.local/bin/gog`.

## Isolation problem

OpenClaw agent isolation covers agent workspaces, state directories, sessions, and identities. It does not automatically isolate third-party CLI credential stores.

`gog` is an external CLI. If it uses the default config directory for the `ben` Unix user, then all OpenClaw agents running as `ben` may be able to use the same Google OAuth credentials when they can execute `gog`.

For the current family/trusted-agent setup, strict per-agent credential isolation is not required. Instead, use one shared `gog` setup and make the intended Google account explicit on every command with `--client` and `--account`.

This is policy separation, not a hard security boundary. If all agents can run arbitrary shell commands as the same Unix user, they can potentially use any configured shared Google account. Stronger isolation would require per-agent config roots, sandbox policy, separate OS users, containers, or narrower tool permissions.

## Current design

Use the normal `gog` config for Unix user `ben`, with file keyring for SSH/service compatibility:

```bash
gog auth keyring file
```

Shared config paths:

```text
~/.config/gogcli/config.json
~/.config/gogcli/credentials-helen.json
~/.config/gogcli/credentials-ben-personal.json
~/.config/gogcli/credentials-ben-work.json
~/.config/gogcli/keyring/
```

Use named OAuth clients:

- `--client helen` for Helen's Google account.
- `--client ben-personal` for Ben's personal Google account.
- `--client ben-work` for Ben's work Google account.

Use explicit account flags:

```bash
--account <helen-google-account>
```

## Wrapper command

Use `gog-agent` so OpenClaw can run `gog` non-interactively. The wrapper loads `GOG_KEYRING_PASSWORD` from a local secret file if the variable is not already set, then executes `gog`.

Secret path:

```text
~/.openclaw/secrets/gog-keyring-password
```

Wrapper path:

```text
~/bin/gog-agent
```

Wrapper shape:

```bash
#!/usr/bin/env bash
set -euo pipefail

password_file="$HOME/.openclaw/secrets/gog-keyring-password"
if [ -z "${GOG_KEYRING_PASSWORD:-}" ] && [ -r "$password_file" ]; then
  IFS= read -r GOG_KEYRING_PASSWORD < "$password_file"
  export GOG_KEYRING_PASSWORD
fi

exec gog "$@"
```

Do not commit this secret file.

## Initial scope

Start with Google Calendar only.

Setup flow for Helen:

```bash
gog auth credentials set /path/to/client_secret.json --client helen
gog auth add <helen-google-account> --client helen --services calendar --readonly
gog-agent auth list --client helen
```

Setup flow for Freddy / Ben:

```bash
gog auth credentials set /path/to/client_secret.json --client ben-personal
gog auth add bbish007@gmail.com --client ben-personal --services calendar --readonly
gog-agent auth list --client ben-personal

gog auth credentials set /path/to/client_secret.json --client ben-work
gog auth add ben.b@covergenius.com --client ben-work --services calendar --readonly
gog-agent auth list --client ben-work
```

Ben's personal Google account has more than one relevant calendar. Freddy's default calendar view must include:

| Calendar | Query |
|---|---|
| Ben Bishop | `gog-agent --client ben-personal --account bbish007@gmail.com calendar events primary ...` |
| Ben and Helen | `gog-agent --client ben-personal --account bbish007@gmail.com calendar events 'demud4un00nih20kass1tosvig@group.calendar.google.com' ...` |
| Work | `gog-agent --client ben-work --account ben.b@covergenius.com calendar events primary ...` |

List Ben's personal calendars:

```bash
gog-agent --client ben-personal --account bbish007@gmail.com calendar calendars --json --no-input
```

Calendar read test:

```bash
gog-agent --client helen --account <helen-google-account> calendar events primary \
  --from 2026-05-10T00:00:00-07:00 \
  --to 2026-05-17T00:00:00-07:00 \
  --json \
  --no-input
```

Use read-only OAuth scopes where available. If broader scopes are added later, enforce write restrictions through agent instructions and approval policy.

## Timezone caveat

The shared `Ben and Helen` calendar can return event timestamps with a `+01:00` offset while the event timezone says `America/Los_Angeles`. Tom and Freddy now use the workspace-local `gog-calendar-timezones` skill wrapper for calendar event reads so results are normalized before user-facing summaries.

For daily briefings that include shared calendars, prefer a slightly wider query window, normalize with the wrapper, and then filter/present the intended local day. This avoids missing events that appear on adjacent dates because of offset bugs.

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

Freddy follows the same policy for Ben's calendars. Freddy may read Ben's personal and work calendars, summarize schedules, identify conflicts, and find openings. Freddy must ask before calendar writes, RSVPs, invites, notifications, email actions, or access to services beyond the configured calendar scope.

## Future expansion

Recommended order after Calendar works:

1. Contacts read access for better scheduling context.
2. Gmail read access for travel and scheduling context.
3. Gmail draft creation, still approval-gated.
4. Drive and Docs read access.
5. Calendar writes, only after approval behavior is reliable.

Each expansion should use explicit `--client` and `--account` flags and should be documented in the relevant agent workspace.

## Verification

After setup:

```bash
command -v gog
gog auth keyring
gog auth credentials list --client helen
gog-agent auth list --client helen
gog-agent --client helen --account <helen-google-account> calendar events primary --from <iso> --to <iso> --json --no-input
gog-agent auth list --client ben-personal
gog-agent auth list --client ben-work
gog-agent --client ben-personal --account bbish007@gmail.com calendar events primary --week --json --no-input
gog-agent --client ben-personal --account bbish007@gmail.com calendar events 'demud4un00nih20kass1tosvig@group.calendar.google.com' --week --json --no-input
gog-agent --client ben-work --account ben.b@covergenius.com calendar events primary --week --json --no-input
openclaw skills list
```

Expected:

- `gog` is installed.
- Shared `gog` has a `helen` OAuth client.
- Shared `gog` has `ben-personal` and `ben-work` OAuth clients once Freddy calendar setup is complete.
- `gog-agent` can unlock the file keyring non-interactively.
- Tom's workspace documents explicit `gog-agent --client helen --account ...` usage and approval rules.
- Freddy's workspace documents explicit `gog-agent --client ben-personal` and `--client ben-work` usage, including both Ben Bishop and Ben and Helen personal calendars.

## Secret hygiene

Do not commit:

- Google OAuth client secrets.
- `gog` token files.
- Refresh tokens.
- `~/.openclaw/secrets/gog-keyring-password`.
- Helen's actual account address if this repository may be shared.

Use placeholders in public docs and keep real credentials on the Strix Halo box only.
