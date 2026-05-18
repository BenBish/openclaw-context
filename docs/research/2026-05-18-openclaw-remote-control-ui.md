# OpenClaw Remote Control UI Access

**Host**: Fedora Strix Halo box  
**Gateway service**: `openclaw-gateway.service`  
**Gateway port**: `18789`  
**Local Control UI**: `http://127.0.0.1:18789/`

This note documents how to open the OpenClaw web Control UI from a remote laptop.

## Recommended: SSH Tunnel

OpenClaw's gateway binds to loopback by default. Keep it that way and forward the port over SSH:

```bash
ssh -N -L 18789:127.0.0.1:18789 ben@100.104.4.96
```

Then open this URL on the laptop:

```text
http://127.0.0.1:18789/
```

This is the lowest-friction remote path because the browser and WebSocket origin both appear local to the gateway.

## Auth Token

The gateway uses token auth:

```json
{
  "gateway": {
    "auth": {
      "mode": "token"
    }
  }
}
```

Read the current token from the gateway host:

```bash
jq -r '.gateway.auth.token' ~/.openclaw/openclaw.json
```

Do not commit the token to this repository. Paste it into the Control UI only when the UI prompts for gateway auth.

## Optional: Tailscale Serve

OpenClaw also supports Tailscale Serve exposure:

```bash
openclaw gateway --tailscale serve
```

After Serve is configured, use the HTTPS MagicDNS URL from Tailscale, usually:

```text
https://<machine>.<tailnet>.ts.net/
```

Do not add `:18789` when using Tailscale Serve. Serve should terminate HTTPS on port `443` and proxy back to the local gateway.

If the gateway is configured to trust Tailscale identity headers, remote auth can use Tailscale identity instead of manually entering the shared token. Otherwise, the same gateway token is still required.

## Pairing a New Browser or Device

A new browser may need device approval before it can use the Control UI.

On the gateway host:

```bash
openclaw devices list
openclaw devices approve <requestId>
```

If the UI says the device token is invalid or mismatched, rotate or reissue the device token from the device management flow rather than reusing stale browser state.

## Troubleshooting

Check the gateway process:

```bash
systemctl --user status openclaw-gateway.service --no-pager
```

Check local HTTP reachability:

```bash
curl -I http://127.0.0.1:18789/
```

Expected result:

```text
HTTP/1.1 200 OK
```

If a direct Tailscale URL such as `https://<machine>.<tailnet>.ts.net:18789/` loads the page but WebSocket connections fail with `origin not allowed`, use the SSH tunnel or configure the gateway Control UI allowed origins for that HTTPS origin.

If logs show:

```text
Proxy headers detected from untrusted address
```

then the gateway is seeing proxy headers from a reverse proxy or Tailscale Serve path that is not in `gateway.trustedProxies`. Use the documented Tailscale Serve setup or add the proxy to the trusted proxy configuration.

## References

- OpenClaw remote gateway docs: https://docs.openclaw.ai/gateway/remote
- OpenClaw Control UI docs: https://docs.openclaw.ai/web/control-ui
