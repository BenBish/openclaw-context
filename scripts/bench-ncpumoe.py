#!/usr/bin/env python3
"""Sweep --n-cpu-moe values for GPT-OSS 120B on Strix Halo.

Restarts llama-server for each configuration, runs two workloads
(short JSON and long agent-style), and records llama.cpp timings.

Usage:
    python scripts/bench-ncpumoe.py
    python scripts/bench-ncpumoe.py --configs 35,20,0
    python scripts/bench-ncpumoe.py --dry-run

Outputs:
    scripts/bench-ncpumoe-results-YYYY-MM-DD.csv
    Markdown summary table printed to stdout.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL = (
    "/home/ben/AI/models/gpt-oss/UD-Q4_K_XL/"
    "gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf"
)
CONTAINER = "llama-rocm-7.2.2"
PORT = 12346
HEALTH_URL = f"http://localhost:{PORT}/health"
CHAT_URL = f"http://localhost:{PORT}/v1/chat/completions"
HEALTH_TIMEOUT_S = 180
KILL_WAIT_S = 5

# Flags held constant across all configs.
FIXED_FLAGS = (
    f"-m {MODEL} "
    "-ngl 99 "
    "-fa 1 "
    "-c 131072 "
    "-b 2048 "
    "-ub 2048 "
    "--no-warmup "
    "--jinja "
    "--temp 1.0 "
    "--top-p 1.0 "
    "--top-k 0 "
    "--min-p 0.0 "
    f"--host 0.0.0.0 "
    f"--port {PORT}"
)

DEFAULT_CONFIGS = [35, 30, 20, 10, 0]

# ── Workload definitions ──────────────────────────────────────────────────────

SHORT_MESSAGES = [
    {
        "role": "system",
        "content": (
            "You are a JSON API. Respond only with valid JSON. "
            "No markdown fences, no explanation, no extra text."
        ),
    },
    {
        "role": "user",
        "content": (
            'Return a JSON object with exactly these keys: '
            '"status" (string value "ok"), '
            '"model" (string value "gpt-oss-120b"), '
            '"version" (integer 1), '
            '"ready" (boolean true).'
        ),
    },
]

_LONG_SYSTEM = """\
You are Tom, a personal AI assistant running inside the OpenClaw multi-agent framework.
You have access to the following tools:

file_read(path: str) -> str
  Read the contents of a file. Returns the file contents as a string.

file_edit(path: str, old_text: str, new_text: str) -> str
  Replace old_text with new_text in the file at path. The old_text must match exactly.

dir_list(path: str, recursive: bool = False) -> list[str]
  List files in a directory. Set recursive=True to include subdirectories.

web_fetch(url: str) -> str
  Fetch a web page and return its text content.

shell_run(command: str, timeout: int = 30) -> str
  Run a shell command and return its stdout. Use sparingly.

calendar_list(start: str, end: str) -> list[dict]
  List calendar events between start and end (ISO 8601 format).

telegram_send(chat_id: str, message: str) -> str
  Send a Telegram message. Returns a confirmation string.

Rules:
- Call one tool at a time. Wait for its result before calling the next.
- Never fabricate file contents or web page results.
- When editing files, read them first to verify current content.
- Keep Telegram messages under 1000 characters.
- Do not send Telegram messages without an explicit instruction to do so.
- Format all dates as ISO 8601. Today is 2026-05-18 (Monday).

You are running as a scheduled cron agent for Ben. \
Approach tasks methodically and report results clearly.\
"""

_LONG_TOOL_RESULT = """\
# OpenClaw Context Repository

This repository contains configuration, documentation, and tooling for the \
OpenClaw multi-agent framework running on the Strix Halo home server.

## Directory Structure

- docs/research/   Research notes on model selection and hardware setup
- docs/runbooks/   Operational runbooks for agents, cron jobs, and services
- scripts/         Utility scripts for benchmarking and validation
- configs/         llama-swap model configs and agent definitions

## Active Stack

- llama-server (llama.cpp) on port 12346, inside the llama-rocm-7.2.2 container
- llama-swap proxy on port 8080, routing to llama-server
- openclaw-gateway service on port 8081, providing the OpenClaw API
- Active model: GPT-OSS 120B UD-Q4_K_XL, --n-cpu-moe 35, 131K context

## Active Agents

Tom — personal assistant. Handles daily briefings, reminders, health summaries.
Freddy — code/ops assistant. Handles development tasks and system maintenance.

## Cron Job Inventory

Job                     Schedule        Timeout   Notes
----------------------  --------------  --------  ----------------------------
Tom Daily               07:00 daily     420s      Morning briefing to Telegram
TLDR Briefing           07:30 Mon-Fri   240s      Tech/AI newsletter digest
Freddy Daily            08:00 daily     420s      Dev summary
Weekend Briefing        08:30 Sat-Sun   420s      Extended weekend summary
Health & Birthdays      09:00 daily     420s      Health check + reminders

## Operational Notes

- All timeouts were raised to 420s after the GPT-OSS 120B cutover (2026-05-17).
  Prior model (Qwen/Gemma) completed most jobs in under 60s.
  GPT-OSS 120B typically takes 140-160s per job.
- llama-server must be running before openclaw-gateway starts.
- Run scripts/cron-validate.py to check cron health and runtime history.
- Model cold-load time: approximately 45-60s after container start.
- The iGPU uses a carved-out portion of the 128GB unified memory pool.
  Current config keeps all 35 MoE experts on CPU to avoid late-load stalls.

## Known Issues

- Tool-use traces show occasional recoverable mistakes: invalid dir_list nodes,
  exact-text edit misses, out-of-range file reads. Use deterministic edits for
  config changes and verify manually.
- OpenClaw liveness warnings appear when multiple model calls are concurrent.
  Sessions still complete; monitor rather than act immediately.
- GLM-4.7-Flash is a fast candidate (~29.5 tok/s) but produces markdown fences
  in JSON responses and uses system-level commands instead of --user variants.
  Needs more prompt engineering before production use.\
"""

LONG_MESSAGES = [
    {"role": "system", "content": _LONG_SYSTEM},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_bench_1",
                "type": "function",
                "function": {
                    "name": "file_read",
                    "arguments": json.dumps(
                        {"path": "/home/ben/Dev/openclaw-context/README.md"}
                    ),
                },
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "call_bench_1",
        "content": _LONG_TOOL_RESULT,
    },
    {
        "role": "user",
        "content": (
            "Based on the README, identify the three most important operational "
            "risks for the OpenClaw system. For each risk, propose a specific "
            "and actionable mitigation step with a concrete implementation detail."
        ),
    },
]

WORKLOADS = [
    {"name": "short", "n_runs": 5, "messages": SHORT_MESSAGES, "max_tokens": 150},
    {"name": "long",  "n_runs": 3, "messages": LONG_MESSAGES,  "max_tokens": 400},
]

# ── llama-server lifecycle ────────────────────────────────────────────────────

def _sh(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)

def kill_llama_server() -> None:
    print("  Stopping existing llama-server ...", flush=True)
    _sh(f"podman exec {CONTAINER} pkill -f llama-server", check=False)
    time.sleep(KILL_WAIT_S)

def start_llama_server(n_cpu_moe: int, tag: str) -> str:
    log = f"/tmp/bench-ncpumoe-{tag}-moe{n_cpu_moe}.log"
    cmd = (
        f"podman exec -d "
        f"-w /home/ben "
        f"-e HSA_OVERRIDE_GFX_VERSION=11.5.1 "
        f"{CONTAINER} "
        f"sh -lc 'exec llama-server {FIXED_FLAGS} --n-cpu-moe {n_cpu_moe} > {log} 2>&1'"
    )
    print(f"  Starting llama-server --n-cpu-moe {n_cpu_moe}  (log: {log})", flush=True)
    _sh(cmd)
    return log

def wait_healthy(timeout: int = HEALTH_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout
    dots = 0
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=5) as r:
                if json.loads(r.read()).get("status") == "ok":
                    print()
                    return True
        except Exception:
            pass
        print(".", end="", flush=True)
        dots += 1
        time.sleep(3)
    print()
    return False

def vram_snapshot() -> str:
    """Return a short VRAM summary string from rocm-smi."""
    # Try JSON output first (newer rocm-smi).
    r = _sh(f"podman exec {CONTAINER} rocm-smi --showmeminfo vram --json", check=False)
    if r.returncode == 0 and r.stdout.strip():
        try:
            data = json.loads(r.stdout)
            for card in data.values():
                if not isinstance(card, dict):
                    continue
                total = card.get("VRAM Total Memory (B)") or card.get("vram_total")
                used  = card.get("VRAM Total Used Memory (B)") or card.get("vram_used")
                if total and used:
                    return f"{int(used)/2**30:.1f}/{int(total)/2**30:.1f} GiB"
        except Exception:
            pass

    # Fallback: plain-text output.
    r = _sh(f"podman exec {CONTAINER} rocm-smi --showmeminfo vram", check=False)
    if r.returncode == 0 and r.stdout:
        # Extract first Used/Total pair from text like "VRAM Total Used Memory (B): 7003004928"
        lines = r.stdout.splitlines()
        total = used = None
        for line in lines:
            if "VRAM Total Memory (B)" in line and "Used" not in line:
                try:
                    total = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
            if "VRAM Total Used Memory (B)" in line:
                try:
                    used = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
        if total and used:
            return f"{used/2**30:.1f}/{total/2**30:.1f} GiB"
        return " ".join(lines[:2])[:60]

    return "unavailable"

# ── Benchmarking ──────────────────────────────────────────────────────────────

def post_completion(messages: list, max_tokens: int) -> tuple[dict, float]:
    """Return (response_body, wall_time_seconds)."""
    payload = {
        "model": "benchmark",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 1.0,
        "top_p": 1.0,
        "top_k": 0,
        "min_p": 0.0,
        "stream": False,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        CHAT_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=300) as r:
        body = json.loads(r.read())
    return body, time.monotonic() - t0

def bench_workload(workload: dict) -> dict:
    name      = workload["name"]
    n_runs    = workload["n_runs"]
    messages  = workload["messages"]
    max_tokens = workload["max_tokens"]

    pp_tps_vals  = []
    gen_tps_vals = []
    ttft_vals    = []
    wall_vals    = []

    for i in range(n_runs):
        print(f"    [{name}] run {i+1}/{n_runs} ...", end=" ", flush=True)
        try:
            body, wall = post_completion(messages, max_tokens)
            t = body.get("timings", {})
            gen_tps = t.get("predicted_per_second", 0.0)
            pp_tps  = t.get("prompt_per_second", 0.0)
            # TTFT approximation: prompt eval time (prefill only, not true TTFT).
            ttft    = t.get("prompt_ms", 0.0) / 1000.0
            pp_tps_vals.append(pp_tps)
            gen_tps_vals.append(gen_tps)
            ttft_vals.append(ttft)
            wall_vals.append(wall)
            print(f"{gen_tps:.1f} gen tok/s  wall {wall:.1f}s", flush=True)
        except Exception as exc:
            print(f"ERROR: {exc}", flush=True)

    def _mean_sd(vals: list) -> tuple:
        if not vals:
            return None, None
        m = statistics.mean(vals)
        s = statistics.stdev(vals) if len(vals) > 1 else 0.0
        return m, s

    pp_m,  pp_s  = _mean_sd(pp_tps_vals)
    gen_m, gen_s = _mean_sd(gen_tps_vals)
    ttft_m, _    = _mean_sd(ttft_vals)
    wall_m, _    = _mean_sd(wall_vals)

    return {
        "pp_tps":    pp_m,  "pp_tps_sd":  pp_s,
        "gen_tps":   gen_m, "gen_tps_sd": gen_s,
        "ttft_s":    ttft_m,
        "wall_s":    wall_m,
        "n":         len(pp_tps_vals),
    }

# ── Output helpers ────────────────────────────────────────────────────────────

def _f(val, d: int = 1) -> str:
    return f"{val:.{d}f}" if val is not None else "—"

def _f_pm(mean, sd) -> str:
    if mean is None:
        return "—"
    return f"{mean:.1f} ± {sd:.1f}"

def print_tables(rows: list) -> None:
    print("\n### Short workload (N=5)\n")
    header = "| n-cpu-moe | status | VRAM | pp tok/s | gen tok/s | TTFT≈ (s) | wall (s) |"
    sep    = "|-----------|--------|------|----------|-----------|-----------|----------|"
    print(header)
    print(sep)
    for row in rows:
        if row["status"] != "ok":
            print(f"| {row['n_cpu_moe']} | FAILED | — | — | — | — | — |")
            continue
        print(
            f"| {row['n_cpu_moe']} | ok | {row.get('vram','—')} "
            f"| {_f_pm(row.get('short_pp_tps'), row.get('short_pp_tps_sd'))} "
            f"| {_f_pm(row.get('short_gen_tps'), row.get('short_gen_tps_sd'))} "
            f"| {_f(row.get('short_ttft_s'))} "
            f"| {_f(row.get('short_wall_s'))} |"
        )

    print("\n### Long workload (N=3)\n")
    header = "| n-cpu-moe | status | pp tok/s | gen tok/s | TTFT≈ (s) | wall (s) |"
    sep    = "|-----------|--------|----------|-----------|-----------|----------|"
    print(header)
    print(sep)
    for row in rows:
        if row["status"] != "ok":
            print(f"| {row['n_cpu_moe']} | FAILED | — | — | — | — |")
            continue
        print(
            f"| {row['n_cpu_moe']} | ok "
            f"| {_f_pm(row.get('long_pp_tps'), row.get('long_pp_tps_sd'))} "
            f"| {_f_pm(row.get('long_gen_tps'), row.get('long_gen_tps_sd'))} "
            f"| {_f(row.get('long_ttft_s'))} "
            f"| {_f(row.get('long_wall_s'))} |"
        )

CSV_FIELDS = [
    "n_cpu_moe", "status", "vram",
    "short_pp_tps", "short_pp_tps_sd", "short_gen_tps", "short_gen_tps_sd",
    "short_ttft_s", "short_wall_s", "short_n",
    "long_pp_tps",  "long_pp_tps_sd",  "long_gen_tps",  "long_gen_tps_sd",
    "long_ttft_s",  "long_wall_s",  "long_n",
]

def write_csv(rows: list, path: Path) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written to: {path}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--configs",
        default=",".join(str(v) for v in DEFAULT_CONFIGS),
        help="Comma-separated --n-cpu-moe values to test (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would run without touching llama-server",
    )
    args = parser.parse_args()

    configs = [int(v.strip()) for v in args.configs.split(",")]
    tag = date.today().isoformat()
    out_csv = Path(__file__).parent / f"bench-ncpumoe-results-{tag}.csv"

    print(f"n-cpu-moe sweep: {configs}")
    print(f"Output: {out_csv}")
    if args.dry_run:
        print("\n[dry-run] Commands that would be executed:")
        for n in configs:
            log = f"/tmp/bench-ncpumoe-{tag}-moe{n}.log"
            print(f"  podman exec {CONTAINER} pkill -f llama-server")
            print(f"  podman exec -d ... llama-server {FIXED_FLAGS} --n-cpu-moe {n} > {log} 2>&1")
        return

    rows: list[dict] = []

    for n_cpu_moe in configs:
        bar = "=" * 60
        print(f"\n{bar}")
        print(f"Config: --n-cpu-moe {n_cpu_moe}")
        print(bar)

        kill_llama_server()
        start_llama_server(n_cpu_moe, tag)

        print(f"  Waiting for health (up to {HEALTH_TIMEOUT_S}s) ", end="", flush=True)
        if not wait_healthy():
            print(f"  FAILED: llama-server did not become healthy within {HEALTH_TIMEOUT_S}s")
            rows.append({"n_cpu_moe": n_cpu_moe, "status": "FAILED"})
            continue

        elapsed_note = ""
        print(f"  Health OK{elapsed_note}")
        vram = vram_snapshot()
        print(f"  VRAM: {vram}")

        row: dict = {"n_cpu_moe": n_cpu_moe, "status": "ok", "vram": vram}

        for workload in WORKLOADS:
            wname = workload["name"]
            print(f"  Running workload: {wname}")
            stats = bench_workload(workload)
            for k, v in stats.items():
                row[f"{wname}_{k}"] = v

        rows.append(row)

    write_csv(rows, out_csv)
    print_tables(rows)


if __name__ == "__main__":
    main()
