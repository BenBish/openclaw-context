#!/usr/bin/env python3
"""Ad hoc validation for OpenClaw cron jobs.

Default mode is intentionally non-invasive: it reads cron config, checks local
services, lints prompts, and reviews recent run history. Use --run explicitly
when you want to trigger production cron jobs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_HOME = Path.home() / ".openclaw"
DEFAULT_JOBS = DEFAULT_HOME / "cron" / "jobs.json"
DEFAULT_RUNS = DEFAULT_HOME / "cron" / "runs"


class Check:
    def __init__(self, status: str, name: str, detail: str = "") -> None:
        self.status = status
        self.name = name
        self.detail = detail


def run_cmd(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return 124, stdout, f"timed out after {timeout}s\n{stderr}".strip()
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def http_get(url: str, timeout: int = 10) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(2048).decode("utf-8", "replace")
            return 200 <= response.status < 400, f"HTTP {response.status}: {body[:160]}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 - diagnostic tool should report exact failure
        return False, str(exc)


def load_jobs(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("jobs", [])


def recent_runs(runs_dir: Path, job_id: str, limit: int = 10) -> list[dict[str, Any]]:
    path = runs_dir / f"{job_id}.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("action") == "finished":
                rows.append(row)
    return rows[-limit:]


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * pct))
    return ordered[index]


def status_line(check: Check) -> str:
    prefix = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}.get(check.status, check.status.upper())
    if check.detail:
        return f"[{prefix}] {check.name}: {check.detail}"
    return f"[{prefix}] {check.name}"


def add(results: list[Check], status: str, name: str, detail: str = "") -> None:
    results.append(Check(status, name, detail))


def check_cli(results: list[Check]) -> None:
    for label, args in (
        ("openclaw cron status", ["openclaw", "cron", "status"]),
        ("openclaw cron list", ["openclaw", "cron", "list"]),
    ):
        code, stdout, stderr = run_cmd(args, timeout=30)
        if code == 0:
            add(results, "ok", label)
        else:
            add(results, "fail", label, stderr or stdout or f"exit {code}")

    code, stdout, stderr = run_cmd(["openclaw", "gateway", "status"], timeout=30)
    if code == 0 and "Connectivity probe: failed" not in stdout:
        add(results, "ok", "openclaw gateway status")
    elif code == 0:
        add(results, "warn", "openclaw gateway status", "command ran, but connectivity probe failed")
    else:
        add(results, "fail", "openclaw gateway status", stderr or stdout or f"exit {code}")


def check_model(results: list[Check]) -> None:
    ok, detail = http_get("http://127.0.0.1:8080/v1/models", timeout=10)
    add(results, "ok" if ok else "fail", "llama-swap /v1/models", detail)

    ok, detail = http_get("http://127.0.0.1:12346/health", timeout=10)
    status = "ok" if ok and '"ok"' in detail else "warn" if ok else "fail"
    add(results, status, "llama-server /health", detail)


def check_job_config(results: list[Check], jobs: list[dict[str, Any]], runs_dir: Path) -> None:
    enabled = [job for job in jobs if job.get("enabled", True)]
    if enabled:
        add(results, "ok", "enabled cron jobs", f"{len(enabled)} enabled")
    else:
        add(results, "fail", "enabled cron jobs", "none enabled")

    for job in enabled:
        job_id = job.get("id", "<missing-id>")
        name = job.get("name", job_id)
        prefix = f"{name} ({job_id})"
        payload = job.get("payload") or {}
        message = payload.get("message") or ""
        timeout = int(payload.get("timeoutSeconds") or 30)
        delivery = job.get("delivery") or {}

        if payload.get("kind") != "agentTurn":
            add(results, "warn", prefix, f"unexpected payload kind: {payload.get('kind')}")

        if timeout < 120:
            add(results, "warn", f"{prefix} timeout", f"{timeout}s is low for local model cron")

        if delivery.get("mode") == "announce" and delivery.get("channel") and delivery.get("to"):
            add(results, "ok", f"{prefix} delivery", f"{delivery.get('channel')} -> {delivery.get('to')}")
        else:
            add(results, "fail", f"{prefix} delivery", "missing announce channel or destination")

        if job.get("failureAlert"):
            add(results, "ok", f"{prefix} failure alert")
        else:
            add(results, "warn", f"{prefix} failure alert", "not configured")

        lint_prompt(results, prefix, message)
        runtime_history(results, prefix, runs_dir, job_id, timeout)


def lint_prompt(results: list[Check], prefix: str, message: str) -> None:
    hard_date = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", message)
    if hard_date:
        add(results, "warn", f"{prefix} prompt", f"hard-coded date {hard_date.group(0)}")

    if "calendar events" in message and "--all-pages" not in message and "--all " not in message:
        add(results, "warn", f"{prefix} prompt", "calendar query may be paginated/truncated")

    if "--all-pages" in message and "compact-events.py" not in message and "Daily Briefing" not in prefix:
        add(results, "warn", f"{prefix} prompt", "large calendar output without compaction")

    if "tldr.tech" in message.lower() and "Do not search the web" not in message:
        add(results, "warn", f"{prefix} prompt", "TLDR prompt does not forbid search drift")

    if "raw page source" in message or "raw HTML" in message:
        add(results, "ok", f"{prefix} prompt", "guards against raw HTML scraping")


def runtime_history(results: list[Check], prefix: str, runs_dir: Path, job_id: str, timeout: int) -> None:
    runs = recent_runs(runs_dir, job_id, limit=10)
    if not runs:
        add(results, "warn", f"{prefix} history", "no finished run history")
        return

    failures = [run for run in runs if run.get("status") != "ok"]
    durations = [int(run.get("durationMs") or 0) for run in runs if run.get("durationMs")]
    p95 = percentile(durations, 0.95)
    last = runs[-1]
    detail = f"last={last.get('status')} p95={p95 / 1000:.1f}s timeout={timeout}s"
    if last.get("status") != "ok":
        add(results, "fail", f"{prefix} history", detail)
    elif p95 > timeout * 1000 * 0.9:
        add(results, "fail", f"{prefix} history", detail)
    elif p95 > timeout * 1000 * 0.75 or failures:
        add(results, "warn", f"{prefix} history", f"{detail}; failures in last 10={len(failures)}")
    else:
        add(results, "ok", f"{prefix} history", detail)


def check_script_paths(results: list[Check], jobs: list[dict[str, Any]]) -> None:
    pattern = re.compile(r"(/home/ben/[^\s'\"|)]+)")
    paths: set[str] = set()
    for job in jobs:
        message = ((job.get("payload") or {}).get("message") or "")
        for match in pattern.finditer(message):
            value = match.group(1).rstrip(",.")
            if value.endswith((".sh", ".py")):
                paths.add(value)

    for path in sorted(paths):
        if Path(path).exists():
            add(results, "ok", f"required script {path}")
        else:
            add(results, "fail", f"required script {path}", "missing")


def check_calendar_auth(results: list[Check], jobs: list[dict[str, Any]]) -> None:
    message_blob = "\n".join(((job.get("payload") or {}).get("message") or "") for job in jobs)
    clients = sorted(set(re.findall(r"--client\s+([A-Za-z0-9_-]+)", message_blob)))
    for client in clients:
        code, stdout, stderr = run_cmd(["gog-agent", "auth", "list", "--client", client], timeout=30)
        if code != 0:
            add(results, "fail", f"gog-agent auth {client}", stderr or stdout or f"exit {code}")
        elif "No authenticated accounts" in stdout or not stdout.strip():
            add(results, "fail", f"gog-agent auth {client}", "no authenticated accounts found")
        else:
            add(results, "ok", f"gog-agent auth {client}")


def check_external_deps(results: list[Check], jobs: list[dict[str, Any]]) -> None:
    today = dt.datetime.now().strftime("%Y-%m-%d")
    urls = [
        "https://tldr.tech/",
        f"https://tldr.tech/tech/{today}",
        f"https://tldr.tech/ai/{today}",
        "https://www.nytimes.com/section/technology",
        "https://wttr.in/San+Francisco?format=j1",
    ]
    message_blob = "\n".join(((job.get("payload") or {}).get("message") or "") for job in jobs).lower()
    for url in urls:
        if "tldr.tech" in url and "tldr.tech" not in message_blob:
            continue
        if "nytimes.com" in url and "nytimes.com" not in message_blob:
            continue
        if "wttr.in" in url and "wttr.in" not in message_blob and "weather" not in message_blob:
            continue
        ok, detail = http_get(url, timeout=15)
        add(results, "ok" if ok else "warn", f"external {url}", detail)


def find_run(job_id: str, run_id: str) -> dict[str, Any] | None:
    code, stdout, _stderr = run_cmd(["openclaw", "cron", "runs", "--id", job_id, "--limit", "20"], timeout=30)
    if code != 0:
        return None
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    for entry in payload.get("entries", []):
        if entry.get("runId") == run_id:
            return entry
    return None


def wait_for_run(job_id: str, run_id: str, timeout_ms: int) -> tuple[str, str]:
    deadline = time.monotonic() + (timeout_ms / 1000)
    last_detail = "run not visible in history yet"
    while time.monotonic() < deadline:
        entry = find_run(job_id, run_id)
        if entry:
            status = entry.get("status")
            duration = entry.get("durationMs")
            delivery = entry.get("deliveryStatus", "unknown")
            if status == "ok":
                return "ok", f"runId={run_id} duration={duration}ms delivery={delivery}"
            if status == "error":
                return "fail", f"runId={run_id} duration={duration}ms error={entry.get('error', 'unknown')}"
            last_detail = f"runId={run_id} status={status}"
        time.sleep(5)
    return "fail", f"timed out waiting for final status; {last_detail}"


def run_production_crons(target: str, jobs: list[dict[str, Any]], timeout_ms: int) -> list[Check]:
    results: list[Check] = []
    selected = jobs if target == "all" else [job for job in jobs if job.get("id") == target or job.get("name") == target]
    if not selected:
        add(results, "fail", "production run selection", f"no job matched {target}")
        return results

    for job in selected:
        job_id = job["id"]
        name = job.get("name", job_id)
        code, stdout, stderr = run_cmd(
            ["openclaw", "cron", "run", job_id, "--expect-final", "--timeout", str(timeout_ms)],
            timeout=max(30, timeout_ms // 1000 + 30),
        )
        if code != 0:
            add(results, "fail", f"run {name}", stderr or stdout or f"exit {code}")
            continue

        run_id = ""
        try:
            payload = json.loads(stdout)
            run_id = payload.get("runId", "")
        except json.JSONDecodeError:
            pass

        if not run_id:
            add(results, "ok", f"run {name}", stdout[:300])
            continue

        status, detail = wait_for_run(job_id, run_id, timeout_ms)
        add(results, status, f"run {name}", detail)
    return results


def render(results: list[Check]) -> int:
    for check in results:
        print(status_line(check))
    fails = sum(1 for item in results if item.status == "fail")
    warns = sum(1 for item in results if item.status == "warn")
    oks = sum(1 for item in results if item.status == "ok")
    print()
    print(f"Summary: {oks} ok, {warns} warn, {fails} fail")
    if fails:
        return 2
    if warns:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate OpenClaw cron jobs without changing schedules.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              scripts/cron-validate.py
              scripts/cron-validate.py --deps
              scripts/cron-validate.py --run 409892b3-44f2-4834-9680-f8ca20c26e1e
            """
        ),
    )
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS, help="cron jobs.json path")
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS, help="cron run history directory")
    parser.add_argument("--quick", action="store_true", help="default mode: config, gateway, model, and history checks")
    parser.add_argument("--deps", action="store_true", help="probe job-specific local and external dependencies")
    parser.add_argument("--run", metavar="JOB_ID_OR_NAME", help="trigger a production cron job, or 'all'")
    parser.add_argument("--run-timeout-ms", type=int, default=360_000, help="timeout for --run checks")
    args = parser.parse_args()

    results: list[Check] = []
    if not args.jobs.exists():
        add(results, "fail", "cron jobs file", f"missing: {args.jobs}")
        return render(results)

    jobs = load_jobs(args.jobs)
    add(results, "ok", "cron jobs file", f"{args.jobs}")
    check_cli(results)
    check_model(results)
    check_job_config(results, jobs, args.runs_dir)

    if args.deps:
        check_script_paths(results, jobs)
        check_calendar_auth(results, jobs)
        check_external_deps(results, jobs)

    if args.run:
        add(
            results,
            "warn",
            "production cron run",
            "this mode triggers real jobs and may deliver Telegram messages",
        )
        results.extend(run_production_crons(args.run, jobs, args.run_timeout_ms))

    return render(results)


if __name__ == "__main__":
    sys.exit(main())
