---
title: GPT-OSS 120B on Strix Halo
date: 2026-05-17
tags: [llm, llama-cpp, gpt-oss, rocm, strix-halo, openclaw]
status: published
---

# GPT-OSS 120B on Strix Halo

Implementation notes for moving OpenClaw from the earlier Qwen/Gemma pair to GPT-OSS 120B on the Fedora Strix Halo box.

## Current Working Setup

OpenClaw uses llama-swap on `http://localhost:8080/v1`, which proxies to a single llama-server process on port `12346`.

Active model:

```text
/home/ben/AI/models/gpt-oss/UD-Q4_K_XL/gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf
```

The Q4 model is split across two GGUF files in:

```text
/home/ben/AI/models/gpt-oss/UD-Q4_K_XL/
```

llama.cpp is pointed at the first shard and loads the second shard automatically.

## Working llama-server Command

Run from the `llama-rocm-7.2.2` toolbox container:

```bash
podman exec -d \
  -w /home/ben \
  -e HSA_OVERRIDE_GFX_VERSION=11.5.1 \
  llama-rocm-7.2.2 \
  sh -lc 'exec llama-server \
    -m /home/ben/AI/models/gpt-oss/UD-Q4_K_XL/gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf \
    -ngl 99 \
    --n-cpu-moe 35 \
    -fa 1 \
    -c 131072 \
    -b 2048 \
    -ub 2048 \
    --no-warmup \
    --jinja \
    --temp 1.0 \
    --top-p 1.0 \
    --top-k 0 \
    --min-p 0.0 \
    --host 0.0.0.0 \
    --port 12346 \
    > /tmp/gpt-oss-120b-q4-cpumoe-12346.log 2>&1'
```

Health check:

```bash
curl http://127.0.0.1:12346/health
```

Expected response:

```json
{"status":"ok"}
```

llama-swap smoke test:

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf","messages":[{"role":"user","content":"Reply with exactly this word and no punctuation: ready"}],"max_tokens":64}'
```

Expected final content:

```text
ready
```

## What Did Not Work

The first F16 attempt used:

```bash
-m /home/ben/AI/models/gpt-oss/gpt-oss-120b-F16.gguf \
-ngl 999 \
-fa 1 \
-c 131072 \
-b 2048 \
-ub 1024 \
--cache-type-k q8_0 \
--cache-type-v q8_0 \
--jinja \
--temp 0.35 \
--top-p 0.95 \
--min-p 0.02
```

The process bound port `12346`, loaded model metadata, and offloaded layers, but `/health` stayed at:

```json
{"error":{"message":"Loading model","type":"unavailable_error","code":503}}
```

The same late-load stall also happened with the Q4 model when all layers and MoE experts were effectively pushed to GPU:

```bash
-ngl 999 \
-c 131072 \
--cache-type-k q8_0 \
--cache-type-v q8_0
```

In both failed cases, llama.cpp showed layer offload progress but never reached:

```text
main: model loaded
main: server is listening on http://0.0.0.0:12346
```

## Key Learnings

- GPT-OSS 120B needs MoE-specific placement. `--n-cpu-moe 35` was the critical flag that made the 131k context run start successfully.
- `--no-warmup` avoids the startup path that appeared to hang during the large full-context warmup.
- Start without KV quantization flags. The working run uses default f16 KV. Reintroduce `--cache-type-k q8_0 --cache-type-v q8_0` only after the baseline remains stable.
- Use `-ngl 99`, not `-ngl 999`, for this setup. The working run still reports `37/37` layers offloaded, while MoE tensors are kept on CPU.
- The Q4 split GGUF is loaded by passing the first shard path. Do not concatenate the shard files manually.
- GPT-OSS may spend tokens in `reasoning_content`; very small `max_tokens` can return no final `content`. Smoke tests should allow enough output tokens.

## llama-swap Config

Active llama-swap model entry:

```yaml
models:
  "gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf":
    cmd: "tail -f /dev/null"
    proxy: http://127.0.0.1:12346
    name: "GPT-OSS 120B UD-Q4_K_XL"
    description: "GPT-OSS 120B local model, UD-Q4_K_XL, 131K context"
    metadata:
      params: "116.83B"
      quantization: "UD-Q4_K_XL"
      context: 131072
      jinja: true
```

`cmd: "tail -f /dev/null"` preserves the current pattern where llama-server is managed externally and llama-swap acts only as a router.

## OpenClaw Config

OpenClaw primary model:

```json
"primary": "local-llama/gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf"
```

Provider endpoint:

```json
"baseUrl": "http://localhost:8080/v1"
```

Model registry values:

```json
{
  "id": "gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf",
  "name": "GPT-OSS 120B UD-Q4_K_XL",
  "api": "openai-completions",
  "contextWindow": 131072,
  "contextTokens": 131072,
  "maxTokens": 4096,
  "input": ["text"]
}
```

## Operational Checks

```bash
systemctl --user status llama-swap.service --no-pager
systemctl --user status openclaw-gateway.service --no-pager
curl http://127.0.0.1:8080/v1/models
curl http://127.0.0.1:12346/health
```

Useful log:

```text
/tmp/gpt-oss-120b-q4-cpumoe-12346.log
```

Successful startup includes:

```text
main: model loaded
main: server is listening on http://0.0.0.0:12346
main: starting the main loop...
```

## Operational Assessment After Cutover

Log review on 2026-05-17 showed the GPT-OSS Q4 backend itself was healthy:

- `llama-server` was listening on `0.0.0.0:12346`.
- `llama-swap` was listening on `:8080`.
- Recent llama-swap `/v1/chat/completions` calls returned HTTP `200`.
- Today’s GPT-OSS OpenClaw trajectories ended with `success`, with no prompt or idle timeouts.
- The llama.cpp log showed successful requests and no response truncation in the reviewed tail.

Issues and follow-ups found during the review:

- Resolved: The Weekend Briefing cron payload had hard-coded `--target-date 2026-05-16` and `Weekend Briefing - Sat, May 16, 2026`. This was a cron prompt/config issue, not a llama-server issue. The payload was updated to use a dynamic date and title format.
- Resolved: The Health, Birthdays & Anniversaries cron job had a manual run time out after about 305 seconds near the model cutover. It was re-run successfully after the GPT-OSS setup stabilized.
- GPT-OSS is substantially slower than the earlier Qwen/Gemma setup. Normal cron jobs were observed around 140-160 seconds, with some interactive requests exceeding one minute. If heavier jobs continue to approach 300 seconds, raise cron `timeoutSeconds` or reduce concurrency.
- OpenClaw logged liveness and stalled-session warnings while multiple model calls were active. The reviewed sessions still completed successfully, so this is a monitoring/tuning concern rather than an immediate failure.
- Tool-use traces showed recoverable mistakes such as invalid `dir_list` nodes, exact-text edit misses, and out-of-range file reads. For important config changes, keep using deterministic edits plus manual verification.

## Candidate Model Follow-Up

Follow-up testing compared the current Q4 setup against GPT-OSS 120B `UD-Q6_K_XL` and GLM-4.7-Flash `UD-Q8_K_XL`.

Short exact-output benchmark:

| Model | Wall time | Generation | Result |
| --- | ---: | ---: | --- |
| GPT-OSS 120B `UD-Q4_K_XL` | 11.0s | 24.6 tok/s | Valid JSON |
| GPT-OSS 120B `UD-Q6_K_XL` | 10.2s | 23.8 tok/s | Valid JSON |
| GLM-4.7-Flash `UD-Q8_K_XL` | 2.4-2.6s | 29.5 tok/s | Needed stricter prompt to avoid Markdown fences |

OpenClaw-specific command prompt:

- GLM was fast but combined two requested commands with `&&` and used system-level `systemctl` instead of `systemctl --user`.
- GPT-OSS Q6 used `systemctl --user` correctly but invented `openclaw validate` instead of using a real JSON validation command.

Recommendation after this pass:

- Keep GPT-OSS 120B `UD-Q4_K_XL` as the active OpenClaw model.
- Do not switch to GPT-OSS Q6 yet; it did not show a meaningful speed or tool-use quality improvement over Q4.
- Keep GLM-4.7-Flash Q8 as a promising fast candidate, but only test it further with OpenClaw agent prompts that explicitly forbid Markdown fences and clarify user-service commands.
- Continue treating config edits as deterministic/manual-review work regardless of model choice.
