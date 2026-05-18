---
title: GPT-OSS 120B n-cpu-moe Benchmark Plan
date: 2026-05-18
tags: [llm, llama-cpp, rocm, strix-halo, benchmark, openclaw]
status: draft
---

# GPT-OSS 120B n-cpu-moe Benchmark Plan

Plan for testing `--n-cpu-moe` configurations on Tuesday, May 19, 2026.

## Goal

Find the best `--n-cpu-moe` setting for the current OpenClaw GPT-OSS 120B local model while keeping the required 131k context window.

The current working baseline is:

```bash
--n-cpu-moe 35
```

The test should prefer the lowest CPU MoE setting that:

- starts reliably with `-c 131072`
- avoids active swap churn during requests
- improves or matches baseline latency and throughput
- lowers CPU pressure without creating GPU, memory, or I/O instability
- preserves acceptable OpenClaw command/tool behavior

## Context

Current active model:

```text
/home/ben/AI/models/gpt-oss/UD-Q4_K_XL/gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf
```

Current runtime pattern:

```text
llama-server runs inside podman container: llama-rocm-7.2.2
llama-server listens on: http://127.0.0.1:12346
llama-swap proxies from: http://127.0.0.1:8080/v1
llama-swap config: ~/.config/llama-swap/config.yaml
```

Keep `-c 131072` fixed. We have observed that smaller context windows are not sufficient for OpenClaw usage because the context window fills up.

Run one candidate at a time by replacing the active `llama-server`. Do not run a second 120B server in parallel: the model, KV cache, ROCm shared-memory behavior, and zram swap state would contaminate the result and may cause avoidable failures.

## Test Matrix

Test these values, changing only `--n-cpu-moe`:

```text
0
10
20
35
```

Use `35` as the baseline and restoration fallback.

Only test higher values such as `45` or `50` if all lower settings fail or if `35` is stable but still CPU/I/O constrained enough to justify another comparison.

## Fixed Server Command

Template command:

```bash
podman exec -d \
  -w /home/ben \
  -e HSA_OVERRIDE_GFX_VERSION=11.5.1 \
  llama-rocm-7.2.2 \
  sh -lc 'exec llama-server \
    -m /home/ben/AI/models/gpt-oss/UD-Q4_K_XL/gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf \
    -ngl 99 \
    --n-cpu-moe REPLACE_ME \
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
    > /tmp/gpt-oss-120b-q4-cpumoe-REPLACE_ME-12346.log 2>&1'
```

## Procedure

Before changing anything, capture baseline host state:

```bash
date
free -h
swapon --show
vmstat 1 10
ps -ww -p "$(pgrep -f 'llama-server .*gpt-oss-120b-UD-Q4_K_XL' | head -1)" -o pid,etime,args,%cpu,%mem,rss,vsz,stat
curl -s http://127.0.0.1:12346/health
curl -s http://127.0.0.1:8080/v1/models
```

For each `--n-cpu-moe` value:

1. Stop the active `llama-server`.
2. Start the candidate server on port `12346`.
3. Wait up to 5 minutes for health:

   ```bash
   curl -s http://127.0.0.1:12346/health
   ```

4. If health does not return `{"status":"ok"}`, record startup failure and inspect the candidate log in `/tmp`.
5. If healthy, run the fixed prompt set through `http://127.0.0.1:8080/v1/chat/completions`.
6. Record:
   - startup success or failure
   - time from launch to healthy
   - wall time per prompt
   - tokens/sec if reported by `llama-server`
   - response quality notes for OpenClaw-style command/tool behavior
   - `free -h`
   - `swapon --show`
   - `vmstat 1 10`
   - top CPU and RSS processes
   - whether swap `si` or `so` is non-zero during requests
   - whether I/O wait is materially higher than baseline

After testing all candidates, restore the best-known stable config. If there is no clear winner, restore:

```bash
--n-cpu-moe 35
```

Then confirm:

```bash
curl -s http://127.0.0.1:12346/health
curl -s http://127.0.0.1:8080/v1/models
```

## Prompt Set

Use the same prompts for every candidate. Keep prompts practical and representative of OpenClaw usage.

### Prompt 1: short command accuracy

Ask for the exact command to check the status of a user systemd service. Expected behavior: use `systemctl --user`, not system-level `systemctl`.

### Prompt 2: medium coding/debug reasoning

Use a repo-local debugging or implementation question that requires several reasoning steps but does not need the full context window. Record wall time and whether the answer stays concrete.

### Prompt 3: long-context pressure

Use a large OpenClaw-style context payload or a long repo/document context. The purpose is not to fill all 131k tokens, but to ensure the candidate still behaves acceptably under realistic context load.

### Prompt 4: tool discipline

Ask for a task that should produce a concise shell command or structured plan. Record whether the model adds unsafe assumptions, uses the wrong service scope, or drifts into verbose/non-actionable output.

## Result Table

Fill this in during the test.

| n-cpu-moe | Starts? | Time to healthy | Prompt wall time | Tokens/sec | CPU load | RSS | Swap si/so | I/O wait | Quality notes | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 |  |  |  |  |  |  |  |  |  |  |
| 10 |  |  |  |  |  |  |  |  |  |  |
| 20 |  |  |  |  |  |  |  |  |  |  |
| 35 |  |  |  |  |  |  |  |  |  |  |

## Decision Rule

Choose the lowest `--n-cpu-moe` value that is reliable and at least as good as baseline on latency, throughput, memory behavior, and OpenClaw response quality.

If lower values are faster but unstable, choose stability over speed.

If lower values fail to start, trigger active swap churn, or degrade command/tool behavior, keep `--n-cpu-moe 35`.

## Notes to Preserve

- `--n-cpu-moe 35` is the current known-good setting.
- `--no-warmup` is part of the known-good startup strategy and should stay fixed.
- KV cache should stay at the default f16 for this benchmark unless a separate memory-pressure test is planned.
- Do not change OpenClaw model IDs or llama-swap config during this benchmark unless the active service cannot be restored by restarting `llama-server`.
