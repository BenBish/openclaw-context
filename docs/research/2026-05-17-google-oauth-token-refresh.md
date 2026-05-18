# Google OAuth Token Refresh

**Date**: 2026-05-17

## Context

Freddy's calendar briefings reported that all calendar sources were unavailable because the Google OAuth token had expired:

- Work: no data retrieved.
- Personal / Family: no data retrieved.

The affected `gog` clients are:

- `ben-personal` for `bbish007@gmail.com`
- `ben-work` for `ben.b@covergenius.com`

Freddy's calendar access depends on stored Google refresh tokens for those named `gog` clients.

## Likely cause

The weekly failure pattern strongly suggests that the Google OAuth app backing these clients is still in **Testing** publishing status.

Google's OAuth policy says refresh tokens for an external app in Testing expire after 7 days when sensitive or restricted scopes are requested. Google Calendar scopes are sensitive scopes, so a weekly refresh-token expiry matches this behavior.

Once the OAuth app is moved to **In production**, refresh tokens should no longer have the fixed 7-day Testing expiry.

Refresh tokens can still be invalidated for other reasons, including user revocation, long inactivity, token count limits, password/admin-policy changes, or Workspace session-control policies.

## Fix to do this week

In Google Cloud Console / Google Auth Platform:

1. Open the project that owns the OAuth client credentials used by `gog`.
2. Go to the OAuth app audience / publishing status page.
3. If the app is in **Testing**, publish it to **In production**.
4. Repeat for any separate project used by `ben-personal` or `ben-work`.

Calendar scopes are sensitive. A private, unverified production app may show an unverified-app warning and may be subject to a small-user cap, but that is usually acceptable for personal use.

## Re-auth after publishing

After publishing, refresh both account tokens once:

```bash
gog auth add bbish007@gmail.com \
  --client ben-personal \
  --services calendar \
  --readonly \
  --force-consent

gog auth add ben.b@covergenius.com \
  --client ben-work \
  --services calendar \
  --readonly \
  --force-consent
```

If the browser flow does not work, use manual mode:

```bash
gog auth add bbish007@gmail.com --client ben-personal --services calendar --readonly --force-consent --manual
gog auth add ben.b@covergenius.com --client ben-work --services calendar --readonly --force-consent --manual
```

## Verification

```bash
gog auth doctor --client ben-personal --check
gog auth doctor --client ben-work --check

gog-agent auth list --client ben-personal
gog-agent auth list --client ben-work

gog-agent --client ben-personal --account bbish007@gmail.com calendar events primary --week --json --no-input
gog-agent --client ben-personal --account bbish007@gmail.com calendar events 'demud4un00nih20kass1tosvig@group.calendar.google.com' --week --json --no-input
gog-agent --client ben-work --account ben.b@covergenius.com calendar events primary --week --json --no-input
```

Then rerun the briefing:

```bash
openclaw cron list
openclaw cron run <daily-briefing-job-id> --expect-final --timeout 120000
```

## References

- Google OAuth 2.0 refresh-token expiration behavior: https://developers.google.com/identity/protocols/oauth2#expiration
- Google Auth Platform audience / publishing status: https://support.google.com/cloud/answer/15549945
