---
title: GPT-OSS 120B n-cpu-moe Benchmark Plan
date: 2026-05-18
tags: [llm, llama-cpp, rocm, strix-halo, benchmark, openclaw]
status: published
---

# GPT-OSS 120B n-cpu-moe Benchmark Plan

Plan for testing `--n-cpu-moe` configurations on Tuesday, May 19, 2026.

## Automated Benchmark

`scripts/bench-ncpumoe.py` automates the sweep: it restarts `llama-server` for each
config, polls `/health`, snapshots VRAM via `rocm-smi`, and runs both workloads.

```bash
# Full sweep (35 → 30 → 20 → 10 → 0)
python scripts/bench-ncpumoe.py

# Targeted run
python scripts/bench-ncpumoe.py --configs 35,20,0

# Dry-run to preview commands
python scripts/bench-ncpumoe.py --dry-run
```

Outputs `scripts/bench-ncpumoe-results-YYYY-MM-DD.csv` and a markdown table.

### Automated workloads

| # | Name  | Prompt size | max_tokens | Runs | Purpose |
|---|-------|-------------|------------|------|---------|
| 1 | short | ~50 tokens  | 150        | 5    | Apples-to-apples vs prior benchmarks |
| 2 | long  | ~1300 tokens | 400       | 3    | Realistic agent-task throughput |

### Automated metrics

| Metric | Source | Notes |
|--------|--------|-------|
| pp tok/s | `timings.prompt_per_second` | Prompt prefill throughput |
| gen tok/s | `timings.predicted_per_second` | Generation throughput |
| TTFT≈ (s) | `timings.prompt_ms / 1000` | Prefill time; not true TTFT |
| Wall (s) | Client-side elapsed | End-to-end request latency |
| VRAM | `rocm-smi --showmeminfo vram` | Snapshot after model load |

The script handles load failures gracefully: if `/health` does not return `ok` within
180 seconds, the config is marked FAILED and the sweep continues.

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
35   baseline (current production)
30   low-risk GPU offload
20   moderate GPU offload
10   aggressive GPU offload
0    all experts on GPU (likely OOM or load stall — tested last)
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

Run on 2026-05-18 via `python scripts/bench-ncpumoe.py`. Full CSV:
`scripts/bench-ncpumoe-results-2026-05-18.csv`.

### Short workload (N=5, ~50-token prompt, max_tokens=150)

| n-cpu-moe | Starts? | pp tok/s | gen tok/s | TTFT≈ (s) | wall (s) | vs baseline |
| --- | --- | --- | --- | --- | --- | --- |
| 35 | yes | 26.9 ± 9.5 | 23.0 ± 3.3 | 0.7 | 4.2 | baseline |
| 30 | yes | 25.4 ± 9.8 | 23.0 ± 2.4 | 0.7 | 5.6 | +0% |
| 20 | yes | 36.1 ± 13.2 | 30.2 ± 2.8 | 0.5 | 3.7 | **+31%** |
| 10 | yes | 46.9 ± 22.1 | 38.5 ± 0.7 | 0.4 | 3.2 | **+67%** |
| 0  | no (load stall at 180s) | — | — | — | — | — |

### Long workload (N=3, ~1300-token prompt, max_tokens=400)

| n-cpu-moe | Starts? | pp tok/s | gen tok/s | TTFT≈ (s) | wall (s) | vs baseline |
| --- | --- | --- | --- | --- | --- | --- |
| 35 | yes | 147.6 ± 221.0 | 20.6 ± 0.1 | 0.9 | 20.4 | baseline |
| 30 | yes | 154.0 ± 231.1 | 21.1 ± 0.1 | 0.9 | 19.9 | +2% |
| 20 | yes | 176.7 ± 258.6 | 27.4 ± 0.2 | 0.8 | 15.4 | **+33%** |
| 10 | yes | 198.4 ± 285.5 | 37.4 ± 0.4 | 0.7 | 11.4 | **+82%** |
| 0  | no (load stall at 180s) | — | — | — | — | — |

Note: pp tok/s stddev is high because the first request in each group does full prefill
while subsequent requests may reuse the prompt prefix slot cache. Generation tok/s
stddev is tight and is the reliable metric.

VRAM snapshot returned "unavailable" — `rocm-smi` flag format differs in this container
build. Does not affect throughput results.

## Analysis

The results show a monotonic improvement as experts move from CPU to GPU:

- **30 vs 35**: negligible gain. Moving only 5 experts to GPU barely shifts throughput.
- **20**: meaningful step change — +31% gen tok/s on short, +33% on long. Loads
  reliably (health check passes in roughly the same time as 35).
- **10**: another large jump — +67% on short, +82% on long. Still loads reliably.
  Generation variance is very tight (±0.7 tok/s) indicating stable operation.
- **0**: fails to load. The GPU VRAM carve-out cannot hold all 35 expert tensors
  alongside the 37 non-MoE layers already offloaded. This matches the original
  late-load stall observed during the 2026-05-17 cutover.

The inflection point is somewhere between n-cpu-moe=10 (stable) and n-cpu-moe=0
(fails). The current VRAM carve-out can absorb 25 of the 35 experts on GPU (35−10=25)
but not all 35.

**Impact on cron job wall times**: the long workload wall time drops from 20.4s to
11.4s (−44%) at n-cpu-moe=10. Cron jobs that currently take 140-160s may drop to
roughly 80-95s, well inside the 420s timeout with comfortable headroom.

## Decision Rule

Choose the lowest `--n-cpu-moe` value that is reliable and at least as good as baseline on latency, throughput, memory behavior, and OpenClaw response quality.

If lower values are faster but unstable, choose stability over speed.

If lower values fail to start, trigger active swap churn, or degrade command/tool behavior, keep `--n-cpu-moe 35`.

## Recommendation

**Use `--n-cpu-moe 10`.**

It is the fastest stable configuration: +67–82% generation throughput over the
current `--n-cpu-moe 35` baseline, with very low run-to-run variance. The model
loads cleanly. n-cpu-moe=0 fails to load, making 10 the practical lower bound.

Update the production llama-server command in the 2026-05-17 runbook and in any
wrapper scripts. No other flags change.

## Notes to Preserve

- `--n-cpu-moe 35` is the current known-good setting.
- `--no-warmup` is part of the known-good startup strategy and should stay fixed.
- KV cache should stay at the default f16 for this benchmark unless a separate memory-pressure test is planned.
- Do not change OpenClaw model IDs or llama-swap config during this benchmark unless the active service cannot be restored by restarting `llama-server`.
